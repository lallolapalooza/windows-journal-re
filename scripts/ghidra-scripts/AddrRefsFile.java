//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.nio.file.*;
public class AddrRefsFile extends GhidraScript {
    public void run() throws Exception {
        java.util.List<String> lines = Files.readAllLines(new File(getScriptArgs()[0]).toPath());
        FunctionManager fm = currentProgram.getFunctionManager();
        for (String line : lines) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] parts = line.split("\\s+");
            long v = Long.decode(parts[0]);
            Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
            println("ADDR " + addr + " label=" + (parts.length > 1 ? parts[1] : "") + " refs=" + currentProgram.getReferenceManager().getReferenceCountTo(addr));
            for (Reference r : currentProgram.getReferenceManager().getReferencesTo(addr)) {
                Function f = fm.getFunctionContaining(r.getFromAddress());
                println("  REF " + r.getFromAddress() + " type=" + r.getReferenceType() + " func=" + (f==null?"?":f.getName()) + " entry=" + (f==null?"?":f.getEntryPoint()));
            }
        }
    }
}
