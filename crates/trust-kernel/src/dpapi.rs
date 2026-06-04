//! DPAPI raw-blob protect/unprotect (RED stub — replaced in GREEN).
#![cfg(windows)]

use crate::key::KernelError;

pub fn dpapi_protect(_plaintext: &[u8]) -> Result<Vec<u8>, KernelError> {
    Err(KernelError::Dpapi("not implemented".into()))
}

pub fn dpapi_unprotect(_blob: &[u8]) -> Result<Vec<u8>, KernelError> {
    Err(KernelError::Dpapi("not implemented".into()))
}
