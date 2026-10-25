//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class RefsForStrings extends GhidraScript {
    public void run() throws Exception {
        List<String> needles = Files.readAllLines(new File(getScriptArgs()[0]).toPath());
        Memory mem = currentProgram.getMemory();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        Set<Long> seenFn = new HashSet<>();
        for (String needle : needles) {
            needle = needle.trim();
            if (needle.isEmpty() || needle.startsWith("#")) continue;
            byte[] pat = needle.getBytes("ISO-8859-1");
            int found = 0;
            for (MemoryBlock b : mem.getBlocks()) {
                if (!b.isInitialized()) continue;
                byte[] data = new byte[(int) b.getSize()];
                int got = mem.getBytes(b.getStart(), data);
                for (int i = 0; i + pat.length <= got; i++) {
                    boolean ok = true;
                    for (int j = 0; j < pat.length; j++) {
                        if (data[i + j] != pat[j]) { ok = false; break; }
                    }
                    if (!ok) continue;
                    Address sa = b.getStart().add(i);
                    Address runStart = sa;
                    for (int back = 1; back <= 200; back++) {
                        int bi = i - back;
                        if (bi < 0) break;
                        byte c = data[bi];
                        if (c < 0x20 || c > 0x7e) break;
                        runStart = b.getStart().add(bi);
                    }
                    List<Address> probes = new ArrayList<>();
                    probes.add(sa);
                    if (!runStart.equals(sa)) probes.add(runStart);
                    for (Address p : probes) {
                        for (Reference r : rm.getReferencesTo(p)) {
                            Function f = fm.getFunctionContaining(r.getFromAddress());
                            if (f == null) continue;
                            long key = f.getEntryPoint().getOffset();
                            println("HIT '" + needle + "' addr=" + p + " func=" + f.getName() + " entry=" + f.getEntryPoint() + " new=" + (!seenFn.contains(key)));
                            if (seenFn.add(key)) found++;
                        }
                    }
                }
            }
            println("DONE '" + needle + "' newFuncs=" + found);
        }
    }
}
