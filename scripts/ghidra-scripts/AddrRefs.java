//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
public class AddrRefs extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()[0].split(",")) {
            Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(a.trim()));
            FunctionManager fm = currentProgram.getFunctionManager();
            println("ADDR " + addr + " refs=" + currentProgram.getReferenceManager().getReferenceCountTo(addr));
            for (Reference r : currentProgram.getReferenceManager().getReferencesTo(addr)) {
                Function f = fm.getFunctionContaining(r.getFromAddress());
                println("  REF " + r.getFromAddress() + " type=" + r.getReferenceType() + " func=" + (f==null?"?":f.getName()) + " entry=" + (f==null?"?":f.getEntryPoint()));
            }
        }
    }
}
