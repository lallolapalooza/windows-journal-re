import ctypes, os, uuid, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DLL_DIR = os.path.join(ROOT, 'extracted', 'win7', 'files')
os.add_dll_directory(DLL_DIR)
ole32 = ctypes.WinDLL('ole32')
ole32.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
ole32.CoInitializeEx.restype=ctypes.c_long
ole32.CreateStreamOnHGlobal.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_void_p)]
ole32.CreateStreamOnHGlobal.restype=ctypes.c_long
k32=ctypes.WinDLL('kernel32'); k32.GetModuleHandleW.restype=ctypes.c_void_p
jd=ctypes.WinDLL(os.path.join(DLL_DIR,'journal.dll'))
base=k32.GetModuleHandleW('journal.dll')
CTOR=base+0x2a070
IID=ctypes.create_string_buffer(uuid.UUID('{26213A0B-5A6C-4472-923D-9F29EFF608B2}').bytes_le,16)

def vfn(p,idx,proto):
    vt=ctypes.cast(p,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return proto(vt[idx])

CTORF=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(CTOR)
WRITE=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong))
SEEK=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_longlong,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulonglong))
READ=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong))
RELEASE=ctypes.CFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)

def make_stream(data):
    p=ctypes.c_void_p()
    assert ole32.CreateStreamOnHGlobal(None,1,ctypes.byref(p))==0
    buf=ctypes.create_string_buffer(data,len(data)); wrote=ctypes.c_ulong(0)
    vfn(p,4,WRITE)(p,buf,len(data),ctypes.byref(wrote))
    vfn(p,5,SEEK)(p,0,0,ctypes.byref(ctypes.c_ulonglong(0)))
    return p

def read_stream(p):
    vfn(p,5,SEEK)(p,0,0,ctypes.byref(ctypes.c_ulonglong(0)))
    out=bytearray(); buf=ctypes.create_string_buffer(65536)
    while True:
        got=ctypes.c_ulong(0)
        hr=vfn(p,3,READ)(p,buf,65536,ctypes.byref(got))
        if hr!=0 or got.value==0: break
        out+=buf.raw[:got.value]
    return bytes(out)

def convert(path):
    ole32.CoInitializeEx(None,2)
    data=open(path,'rb').read()
    inp=make_stream(data)
    obj=ctypes.c_void_p()
    hr=CTORF(None,IID,ctypes.byref(obj))
    print('ctor hr',hex(hr&0xffffffff),'obj',hex(obj.value or 0), file=sys.stderr)
    if hr!=0: return None
    out=ctypes.c_void_p()
    fn=vfn(obj,3,ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)))
    hr=fn(obj,inp,ctypes.byref(out))
    print('read hr',hex(hr&0xffffffff),'out',hex(out.value or 0), file=sys.stderr)
    if hr!=0: return None
    xml=read_stream(out)
    vfn(out,2,RELEASE)(out)
    return xml

if __name__=='__main__':
    xml=convert(sys.argv[1])
    if xml is None: sys.exit(1)
    sys.stdout.buffer.write(xml)
