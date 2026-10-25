//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

public class FindScalars extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Set<Long> vals = new HashSet<>();
        for (String a : args[0].split(",")) vals.add(Long.decode(a.trim()));
        FunctionManager fm = currentProgram.getFunctionManager();
        int hits = 0;
        for (Instruction ins = getFirstInstruction(); ins != null && !monitor.isCancelled(); ins = ins.getNext()) {
            for (int op = 0; op < ins.getNumOperands(); op++) {
                for (Object o : ins.getOpObjects(op)) {
                    if (o instanceof Scalar) {
                        long v = ((Scalar) o).getUnsignedValue();
                        if (vals.contains(v)) {
                            Function f = fm.getFunctionContaining(ins.getAddress());
                            println("HIT val=0x" + Long.toHexString(v) + " addr=" + ins.getAddress() +
                                " func=" + (f == null ? "?" : f.getName()) +
                                " entry=" + (f == null ? "?" : f.getEntryPoint()) +
                                " ins=" + ins);
                            hits++;
                        }
                    }
                }
            }
        }
        println("TOTAL " + hits);
    }
}
