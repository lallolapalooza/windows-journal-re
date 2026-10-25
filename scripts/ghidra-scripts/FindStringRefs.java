//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.util.*;

public class FindStringRefs extends GhidraScript {
    public void run() throws Exception {
        String needle = getScriptArgs()[0];
        Memory mem = currentProgram.getMemory();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        Set<Address> addrs = new LinkedHashSet<>();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized()) continue;
            byte[] pat = needle.getBytes("ISO-8859-1");
            long start = 0;
            byte[] data = new byte[(int)b.getSize()];
            int got = mem.getBytes(b.getStart(), data);
            for (int i = 0; i + pat.length <= got; i++) {
                boolean ok = true;
                for (int j = 0; j < pat.length; j++) if (data[i+j] != pat[j]) { ok = false; break; }
                if (ok) addrs.add(b.getStart().add(i));
            }
        }
        println("STRINGS " + addrs.size());
        for (Address a : addrs) {
            println("STR " + a + " refs=" + rm.getReferenceCountTo(a));
            for (Reference r : rm.getReferencesTo(a)) {
                Address from = r.getFromAddress();
                Function f = fm.getFunctionContaining(from);
                println("  REF " + from + " func=" + (f==null?"?":f.getName()) + " entry=" + (f==null?"?":f.getEntryPoint()));
            }
        }
    }
}
