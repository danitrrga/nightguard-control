//! Runtime tray-icon badge renderer — draws the time-remaining count straight onto the tray
//! icon so it is visible at a glance WITHOUT hovering (the Windows tooltip is hover-only).
//!
//! Pure Rust, zero new dependencies (honors the lean-deps constraint): a hand-rolled 5x7 bitmap
//! font is integer-scaled and centered on a 32x32 transparent RGBA canvas, tinted by lock state
//! (cobalt locked / sage open / amber grace / rose unverified) and given a dark 1px outline so it
//! reads on both light and dark taskbars. Advisory display only — the guard stays source of truth.

use tauri::image::Image;

const CANVAS: u32 = 32;
const GW: usize = 5; // glyph width (bits)
const GH: usize = 7; // glyph height (rows)
const MARGIN: usize = 2; // px breathing room inside the canvas
const MAX_SCALE: usize = 4; // cap integer scale so 1-2 char badges stay a consistent weight

/// 5x7 bitmap for a single glyph; each row uses the low 5 bits (MSB = leftmost column).
/// Only the glyphs the badge can emit are defined: digits, 'h', '+', '!'.
fn glyph(c: char) -> Option<[u8; GH]> {
    let g = match c {
        '0' => [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110],
        '1' => [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
        '2' => [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
        '3' => [0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110],
        '4' => [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
        '5' => [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
        '6' => [0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
        '7' => [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
        '8' => [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
        '9' => [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100],
        'h' => [0b10000, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001],
        '+' => [0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000],
        '!' => [0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100],
        _ => return None,
    };
    Some(g)
}

/// Text fill color per lock state (the Ceramic Night palette, brightened for tray legibility).
fn fill_color(state: &str) -> [u8; 3] {
    match state {
        "open" => [0x8f, 0xb3, 0xa3],  // sage
        "grace" => [0xd7, 0xaa, 0x42], // amber
        "warn" => [0xd9, 0x8a, 0x80],  // rose
        _ => [0x6f, 0xa0, 0xff],       // cobalt (locked / default)
    }
}

/// Write a pixel, keeping whichever color has the higher alpha (outline first, fill wins on lit px).
fn put(buf: &mut [u8], x: isize, y: isize, c: [u8; 4]) {
    if x < 0 || y < 0 || x >= CANVAS as isize || y >= CANVAS as isize {
        return;
    }
    let idx = ((y as u32 * CANVAS + x as u32) * 4) as usize;
    if c[3] >= buf[idx + 3] {
        buf[idx..idx + 4].copy_from_slice(&c);
    }
}

/// Render `text` (e.g. "47", "2h", "!") tinted by `state` onto a 32x32 RGBA tray icon.
/// Returns `None` when no drawable glyphs remain (caller restores the default brand icon).
pub fn render_badge(text: &str, state: &str) -> Option<Image<'static>> {
    let glyphs: Vec<[u8; GH]> = text.chars().filter_map(glyph).collect();
    if glyphs.is_empty() {
        return None;
    }
    let n = glyphs.len();
    let text_w = n * GW + (n - 1); // 1px inter-glyph spacing
    let avail = CANVAS as usize - 2 * MARGIN;
    let scale = (avail / text_w).min(avail / GH).clamp(1, MAX_SCALE);

    let px_w = text_w * scale;
    let px_h = GH * scale;
    let ox = (CANVAS as usize - px_w) / 2;
    let oy = (CANVAS as usize - px_h) / 2;

    // Collect every lit (scaled) text pixel.
    let mut lit: Vec<(isize, isize)> = Vec::new();
    for (gi, g) in glyphs.iter().enumerate() {
        let gx0 = ox + gi * (GW + 1) * scale;
        for (ry, row) in g.iter().enumerate() {
            for cx in 0..GW {
                if (row >> (GW - 1 - cx)) & 1 == 1 {
                    for sy in 0..scale {
                        for sx in 0..scale {
                            lit.push(((gx0 + cx * scale + sx) as isize, (oy + ry * scale + sy) as isize));
                        }
                    }
                }
            }
        }
    }

    let mut buf = vec![0u8; (CANVAS * CANVAS * 4) as usize];
    // Dark outline (8-neighbour) first for contrast on light taskbars...
    let outline = [0x08, 0x0a, 0x0e, 220];
    for &(x, y) in &lit {
        for dy in -1..=1 {
            for dx in -1..=1 {
                put(&mut buf, x + dx, y + dy, outline);
            }
        }
    }
    // ...then the state-tinted fill on top.
    let c = fill_color(state);
    let fill = [c[0], c[1], c[2], 255];
    for &(x, y) in &lit {
        put(&mut buf, x, y, fill);
    }

    Some(Image::new_owned(buf, CANVAS, CANVAS))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Count opaque (alpha 255) pixels — the state-tinted fill, excluding the semi-opaque outline.
    fn opaque_px(img: &Image<'_>) -> usize {
        img.rgba().chunks_exact(4).filter(|p| p[3] == 255).count()
    }

    #[test]
    fn renders_a_canvas_sized_badge() {
        let img = render_badge("47", "locked").expect("drawable digits");
        assert_eq!(img.width(), CANVAS);
        assert_eq!(img.height(), CANVAS);
        assert_eq!(img.rgba().len(), (CANVAS * CANVAS * 4) as usize);
        assert!(opaque_px(&img) > 0, "fill pixels must be drawn");
    }

    #[test]
    fn empty_or_undrawable_text_yields_none() {
        // Empty -> caller restores the plain brand icon.
        assert!(render_badge("", "open").is_none());
        // No glyph in the font for these chars.
        assert!(render_badge("@#", "open").is_none());
    }

    #[test]
    fn state_picks_the_palette_fill() {
        // The fill color of a lit pixel reflects the state tint (sage for open, cobalt for locked).
        let open = render_badge("8", "open").unwrap();
        let locked = render_badge("8", "locked").unwrap();
        let first_fill = |img: &Image<'_>| -> [u8; 3] {
            let p = img
                .rgba()
                .chunks_exact(4)
                .find(|p| p[3] == 255)
                .expect("a fill pixel");
            [p[0], p[1], p[2]]
        };
        assert_eq!(first_fill(&open), fill_color("open"));
        assert_eq!(first_fill(&locked), fill_color("locked"));
        assert_ne!(first_fill(&open), first_fill(&locked));
    }

    #[test]
    fn unknown_state_falls_back_to_locked_cobalt() {
        assert_eq!(fill_color("nonsense"), fill_color("locked"));
    }

    #[test]
    fn multi_glyph_hours_badge_is_drawable() {
        let img = render_badge("12h", "grace").expect("digits + h");
        assert!(opaque_px(&img) > 0);
    }
}
