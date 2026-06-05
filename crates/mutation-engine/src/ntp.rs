//! RULE-05 (true-time half): SNTP true-time behind a [`TrueTime`] trait.
//!
//! True time is obtained from SNTP via `sntpc` 0.10.1 + `sntpc-net-std`. Any SNTP error
//! (unreachable / DNS failure / timeout / malformed response) maps to a typed
//! [`NtpUnreachable`] refusal. The app/system clock is NEVER consulted as a fallback —
//! "no verified true time" means "refuse anything time-gated" (grace), which is the
//! fail-closed property of threat T-02-08.
//!
//! The live UDP path is hidden behind the [`TrueTime`] trait so plan 02-04's quota/grace
//! logic is fully offline-testable with an injected [`FakeTrueTime`]; only the `#[ignore]`
//! live integration test touches a real socket. This is the one no-analog module — no
//! networking existed in Phase 1.
//!
//! Invariant (anti-pattern guarded against): no code path in this module returns
//! `SystemTime::now()` / `Local::now()` on SNTP failure. Failure always yields
//! `NtpUnreachable`.

use std::net::{ToSocketAddrs, UdpSocket};
use std::time::Duration;

use sntpc::{sync::get_time, NtpContext, StdTimestampGen};
use sntpc_net_std::UdpSocketWrapper;

/// A verified true-time instant obtained from SNTP.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NtpTrueTime {
    /// True unix seconds (NTP server `seconds`, NTP→unix epoch already applied by `sntpc`).
    pub unix_secs: i64,
    /// Sub-second fraction (NTP `seconds_fraction`); kept for completeness, grace uses secs.
    pub frac: u32,
    /// Estimated offset (microseconds) between the NTP reference and local system time.
    pub offset: i64,
}

/// True time could not be verified — refuse anything time-gated (RULE-05, fail-closed).
///
/// Folds into [`MutationError::NtpUnreachable`](crate::MutationError::NtpUnreachable) via
/// the provided `From` impl so downstream `?` in commit/grace stays ergonomic.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NtpUnreachable;

impl From<NtpUnreachable> for crate::MutationError {
    fn from(_: NtpUnreachable) -> Self {
        crate::MutationError::NtpUnreachable
    }
}

/// True-time provider. Hiding live UDP behind this trait is what lets quota/grace logic be
/// tested deterministically offline (inject [`FakeTrueTime`]); production uses
/// [`SntpTrueTime`].
pub trait TrueTime {
    /// Obtain verified true time, or refuse with [`NtpUnreachable`] if it cannot be
    /// established. Implementations MUST NOT fall back to the system/local clock.
    fn now(&self) -> Result<NtpTrueTime, NtpUnreachable>;
}

/// Default fallback NTP host list (Assumption A4). Tried in order; first success wins;
/// all-fail = [`NtpUnreachable`].
const DEFAULT_SERVERS: &[&str] = &["time.cloudflare.com", "time.google.com", "pool.ntp.org"];

/// Production [`TrueTime`] backed by a synchronous SNTP query (RESEARCH Pattern 1).
pub struct SntpTrueTime {
    servers: Vec<String>,
}

impl Default for SntpTrueTime {
    fn default() -> Self {
        SntpTrueTime {
            servers: DEFAULT_SERVERS.iter().map(|s| s.to_string()).collect(),
        }
    }
}

impl SntpTrueTime {
    /// Build with a custom server list (e.g. to reuse the PS hook's configured host).
    /// Empty list means there is no reachable source → `now()` will refuse.
    pub fn new(servers: Vec<String>) -> Self {
        SntpTrueTime { servers }
    }

    /// Query a single host. Any error (bind / timeout setup / DNS / SNTP wire / response)
    /// maps to [`NtpUnreachable`] — never a clock fallback.
    fn query_one(server: &str) -> Result<NtpTrueTime, NtpUnreachable> {
        let socket = UdpSocket::bind("0.0.0.0:0").map_err(|_| NtpUnreachable)?;
        // Offline → recv blocks then times out → SNTP surfaces it as Error::Network.
        socket
            .set_read_timeout(Some(Duration::from_secs(2)))
            .map_err(|_| NtpUnreachable)?;
        let socket = UdpSocketWrapper::new(socket);
        let ctx = NtpContext::new(StdTimestampGen::default());

        let addr = format!("{server}:123")
            .to_socket_addrs()
            .map_err(|_| NtpUnreachable)? // DNS failure
            .find(|a| a.is_ipv4())
            .ok_or(NtpUnreachable)?;

        // `sntpc::Error` is `#[non_exhaustive]`; ANY variant (Network, AddressResolve,
        // timeout-as-Network, malformed response, KissOfDeath, ...) = unverified time =
        // refuse. The catch-all is mandatory and intentional.
        match get_time(addr, &socket, ctx) {
            Ok(res) => Ok(NtpTrueTime {
                unix_secs: i64::from(res.sec()),
                frac: res.sec_fraction(),
                offset: res.offset(),
            }),
            Err(_) => Err(NtpUnreachable),
        }
    }
}

impl TrueTime for SntpTrueTime {
    fn now(&self) -> Result<NtpTrueTime, NtpUnreachable> {
        // Try each host; first success wins. All-fail (or empty list) = NtpUnreachable.
        for server in &self.servers {
            if let Ok(t) = Self::query_one(server) {
                return Ok(t);
            }
        }
        Err(NtpUnreachable)
    }
}

/// Test/offline [`TrueTime`] returning a fixed `Result`, enabling deterministic
/// quota/grace tests (plan 02-04) without any network.
pub struct FakeTrueTime {
    result: Result<NtpTrueTime, NtpUnreachable>,
}

impl FakeTrueTime {
    /// A fake that always yields the given true-time instant.
    pub fn ok(time: NtpTrueTime) -> Self {
        FakeTrueTime { result: Ok(time) }
    }

    /// A fake that always refuses (simulates an offline / unreachable NTP source).
    pub fn unreachable() -> Self {
        FakeTrueTime {
            result: Err(NtpUnreachable),
        }
    }
}

impl TrueTime for FakeTrueTime {
    fn now(&self) -> Result<NtpTrueTime, NtpUnreachable> {
        self.result
    }
}
