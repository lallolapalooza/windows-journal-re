"""OLE property set stream reader/writer helpers for Journal EP pages."""
import struct, uuid

VT_NAMES = {0:'VT_EMPTY',1:'VT_NULL',2:'VT_I2',3:'VT_I4',4:'VT_R4',5:'VT_R8',0x12:'VT_UI2',0x13:'VT_UI4',
            0x1e:'VT_LPWSTR',0x1f:'VT_LPSTR',0x41:'VT_BLOB',0x42:'VT_STREAM',0x43:'VT_STORAGE',0x40:'VT_FILETIME'}

def sections(d):
    n=struct.unpack_from('<I',d,24)[0]
    out=[]
    for i in range(n):
        fmtid=d[28+i*20:44+i*20]
        off=struct.unpack_from('<I',d,44+i*20)[0]
        size,np=struct.unpack_from('<II',d,off)
        out.append((uuid.UUID(bytes_le=bytes(fmtid)), off, size, np))
    return out

def read_props(d, off):
    size,np=struct.unpack_from('<II',d,off)
    props=[]
    for j in range(np):
        pid,poff=struct.unpack_from('<II',d,off+8+j*8)
        p=off+poff
        vt=struct.unpack_from('<I',d,p)[0]
        props.append((pid, vt, p))
    return props

def value_bytes(d, vt, p, count=1):
    if vt in (2,0x12):
        return d[p+4:p+4+2*count]
    if vt in (3,0x13):
        return d[p+4:p+4+4*count]
    if vt in (4,):
        return d[p+4:p+4+4*count]
    if vt in (5,):
        return d[p+4:p+4+8*count]
    if vt==0x1e:
        ln=struct.unpack_from('<I',d,p+4)[0]; return d[p+8:p+8+ln]
    if vt==0x1f:
        ln=struct.unpack_from('<I',d,p+4)[0]; return d[p+8:p+8+ln]
    if vt==0x41:
        ln=struct.unpack_from('<I',d,p+4)[0]; return d[p+8:p+8+ln]
    if vt==0x42:
        ln=struct.unpack_from('<I',d,p+4)[0]; return d[p+8:p+8+ln]
    return b''
