/**
 * MurmurHash3 x86_32 — the cover's deterministic title hash.
 *
 * The variant axis is `murmur3_32(title) % 3`, so the same title must land on
 * the same layout on every render and every machine. That needs the standard
 * algorithm bit for bit, not a lookalike: 32-bit little-endian blocks, the
 * fall-through tail switch and fmix32, with `Math.imul` for the multiplies and
 * `>>> 0` to stay unsigned. The canonical seed-0 vectors pin it: `""` → 0,
 * `"hello"` → 0x248bfa47.
 *
 * The key is hashed as its UTF-8 bytes — the encoding the reference
 * implementations use — so a title with umlauts hashes the same here as
 * anywhere else. Pure: no state, no dependencies.
 */

const C1 = 0xcc9e2d51;
const C2 = 0x1b873593;

/** The final avalanche: every input bit reaches every output bit. */
function fmix32(h: number): number {
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return h >>> 0;
}

/** The unsigned 32-bit MurmurHash3 x86_32 of `key`'s UTF-8 bytes; seed defaults to 0. */
export function murmur3_32(key: string, seed = 0): number {
  const bytes = new TextEncoder().encode(key);
  const length = bytes.length;
  let h1 = seed >>> 0;

  // Body: one 32-bit little-endian block at a time.
  const blocks = length >>> 2;
  for (let i = 0; i < blocks; i += 1) {
    const o = i * 4;
    let k1 = bytes[o] | (bytes[o + 1] << 8) | (bytes[o + 2] << 16) | (bytes[o + 3] << 24);
    k1 = Math.imul(k1, C1);
    k1 = (k1 << 15) | (k1 >>> 17);
    k1 = Math.imul(k1, C2);

    h1 ^= k1;
    h1 = (h1 << 13) | (h1 >>> 19);
    h1 = (Math.imul(h1, 5) + 0xe6546b64) | 0;
  }

  // Tail: the 0–3 bytes the blocks left over, highest byte first.
  let k1 = 0;
  const tail = blocks * 4;
  switch (length & 3) {
    case 3:
      k1 ^= bytes[tail + 2] << 16;
    // falls through
    case 2:
      k1 ^= bytes[tail + 1] << 8;
    // falls through
    case 1:
      k1 ^= bytes[tail];
      k1 = Math.imul(k1, C1);
      k1 = (k1 << 15) | (k1 >>> 17);
      k1 = Math.imul(k1, C2);
      h1 ^= k1;
  }

  h1 ^= length;
  return fmix32(h1);
}