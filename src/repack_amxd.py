import struct, sys, os, zipfile

def make_wave_dire(fname, size, offset):
    name_b = fname.encode("utf-8") + b"\x00"
    while len(name_b) % 4 != 0:
        name_b += b"\x00"
    chunks = (
        b"type" + struct.pack(">I", 12) + b"WAVE" +
        b"fnam" + struct.pack(">I", 8 + len(name_b)) + name_b +
        b"sz32" + struct.pack(">I", 12) + struct.pack(">I", size) +
        b"of32" + struct.pack(">I", 12) + struct.pack(">I", offset) +
        b"vers" + struct.pack(">I", 12) + struct.pack(">I", 0) +
        b"flag" + struct.pack(">I", 12) + struct.pack(">I", 0) +
        b"mdat" + struct.pack(">I", 12) + struct.pack(">I", 0)
    )
    return b"dire" + struct.pack(">I", 8 + len(chunks)) + chunks

def repack(orig_amxd, new_json_path, out_amxd, slices_zip="user_slices.zip"):
    with open(orig_amxd, "rb") as f:
        orig = f.read()
    with open(new_json_path, "rb") as f:
        new_json = f.read().rstrip(b"\x00") + b"\x00"

    toc_start = 32 + struct.unpack(">I", orig[44:48])[0]
    p = toc_start + 8
    sz = struct.unpack(">I", orig[p+4:p+8])[0]
    ep = p + 8
    old_json_sz = 0
    while ep < p + sz:
        st = orig[ep:ep+4]
        ssz = struct.unpack(">I", orig[ep+4:ep+8])[0]
        if st == b"sz32":
            old_json_sz = struct.unpack(">I", orig[ep+8:ep+12])[0]
            break
        ep += ssz

    delta = len(new_json) - old_json_sz
    toc = bytearray(orig[toc_start:])
    pos, idx = 8, 0
    while pos < len(toc):
        tag = toc[pos:pos+4]
        csz = struct.unpack(">I", toc[pos+4:pos+8])[0]
        if tag == b"dire":
            cep = pos + 8
            while cep < pos + csz:
                st = toc[cep:cep+4]
                ssz = struct.unpack(">I", toc[cep+4:cep+8])[0]
                if st == b"sz32" and idx == 0:
                    toc[cep+8:cep+12] = struct.pack(">I", len(new_json))
                elif st == b"of32" and idx > 0:
                    old_of = struct.unpack(">I", toc[cep+8:cep+12])[0]
                    toc[cep+8:cep+12] = struct.pack(">I", old_of + delta)
                cep += ssz
            idx += 1
        pos += csz

    # Append extra WAV slices from user_slices.zip if present
    extra_blobs = bytearray()
    extra_dires = bytearray()
    cur_offset = (toc_start - 32) + delta
    if os.path.exists(slices_zip):
        with zipfile.ZipFile(slices_zip, "r") as zf:
            for name in sorted(zf.namelist()):
                if not name.lower().endswith(".wav"):
                    continue
                blob = zf.read(name)
                extra_dires += make_wave_dire(name, len(blob), cur_offset)
                extra_blobs += blob
                cur_offset += len(blob)

    new_toc = bytes(toc) + bytes(extra_dires)
    new_dlst_len = len(new_toc)
    new_toc = b"dlst" + struct.pack(">I", new_dlst_len) + new_toc[8:]

    body_middle = orig[48+old_json_sz:toc_start]
    new_toc_off = 16 + len(new_json) + len(body_middle) + len(extra_blobs)

    hdr = bytearray(orig[:48])
    hdr[44:48] = struct.pack(">I", new_toc_off)
    new_ptch_len = 16 + len(new_json) + len(body_middle) + len(extra_blobs) + len(new_toc)
    hdr[28:32] = struct.pack("<I", new_ptch_len)

    out_bytes = bytes(hdr) + new_json + body_middle + bytes(extra_blobs) + new_toc
    with open(out_amxd, "wb") as f:
        f.write(out_bytes)
    print(f"Done! Created: {out_amxd} ({len(out_bytes)} bytes, extra_wavs={len(extra_blobs)} bytes)")

if __name__ == "__main__":
    orig = sys.argv[1] if len(sys.argv) > 1 else "formforum - SNARES - SNARE GEN (Rhythm Edition).amxd"
    repack(orig, "IDM_TRAP_GEN.json", "formforum - SNARES - IDM TRAP GEN.amxd")