//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
public class DumpMem extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(args[0]));
        int len = Integer.decode(args[1]);
        FunctionManager fm = currentProgram.getFunctionManager();
        SymbolTable st = currentProgram.getSymbolTable();
        byte[] buf = new byte[len];
        int got = currentProgram.getMemory().getBytes(addr, buf);
        for (int i = 0; i < got; i += 8) {
            long q = 0;
            for (int j = 7; j >= 0; j--) q = (q << 8) | (buf[i+j] & 0xffL);
            String extra = "";
            Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(q);
            Function f = fm.getFunctionAt(a);
            if (f != null) extra = " FUNC=" + f.getName();
            else {
                Symbol s = st.getPrimarySymbol(a);
                if (s != null) extra = " SYM=" + s.getName();
                Data d = getDataAt(a);
                if (d != null) extra = " DATA=" + d.toString();
            }
            println(String.format("%s +%03x = %016x%s", addr, i, q, extra));
        }
    }
}
