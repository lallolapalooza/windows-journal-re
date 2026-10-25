//@category JNT.RE
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class DecompileFns extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outdir = args[0];
        String regex = args.length > 1 ? args[1] : "";
        int limit = args.length > 2 && !args[2].isEmpty() ? Integer.parseInt(args[2]) : 0;
        int timeout = args.length > 3 && !args[3].isEmpty() ? Integer.parseInt(args[3]) : 120;
        boolean addrMode = regex.startsWith("addr:");
        Pattern rx = (regex.isEmpty() || addrMode) ? null : Pattern.compile(regex);
        java.util.List<Long> addrs = new java.util.ArrayList<>();
        if (addrMode) {
            for (String a : regex.substring(5).split(";")) addrs.add(Long.decode(a.trim()));
        }
        new File(outdir).mkdirs();
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface ifc = new DecompInterface();
        ifc.setOptions(new DecompileOptions());
        ifc.openProgram(currentProgram);
        PrintWriter idx = new PrintWriter(new FileWriter(new File(outdir, "index.tsv")));
        int n = 0;
        for (Function f : fm.getFunctions(true)) {
            if (f.isExternal() || f.isThunk()) continue;
            boolean want = rx == null;
            if (rx != null) want = rx.matcher(f.getName()).find();
            if (!want && !addrs.isEmpty()) {
                for (long a : addrs) if (f.getBody().contains(currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(a))) { want = true; break; }
            }
            if (!want) continue;
            if (limit > 0 && n >= limit) break;
            DecompileResults res = ifc.decompileFunction(f, timeout, monitor);
            if (!res.decompileCompleted()) { println("FAIL " + f.getName()); continue; }
            String c = res.getDecompiledFunction().getC();
            String safe = f.getName().replaceAll("[^A-Za-z0-9_.-]+", "_");
            String file = f.getEntryPoint().toString().replace(":", "") + "_" + safe + ".c";
            PrintWriter pw = new PrintWriter(new FileWriter(new File(outdir, file)));
            pw.print(c); pw.close();
            idx.println(f.getEntryPoint() + "\t" + f.getName() + "\t" + file + "\t" + c.length());
            n++;
        }
        idx.close();
        println("DECOMPILED " + n);
    }
}
