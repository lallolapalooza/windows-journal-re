//@category JNT.RE
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public class DecompileByNameFile extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outdir = args[0];
        List<String> names = Files.readAllLines(new File(args[1]).toPath());
        new File(outdir).mkdirs();
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface ifc = new DecompInterface();
        ifc.setOptions(new DecompileOptions());
        ifc.openProgram(currentProgram);
        PrintWriter idx = new PrintWriter(new FileWriter(new File(outdir, "index.tsv"), true));
        int n = 0;
        for (Function f : fm.getFunctions(true)) {
            if (f.isExternal()) continue;
            boolean want = false;
            for (String s : names) { s = s.trim(); if (!s.isEmpty() && f.getName().contains(s)) { want = true; break; } }
            if (!want) continue;
            DecompileResults res = ifc.decompileFunction(f, 180, monitor);
            if (!res.decompileCompleted()) { println("FAIL " + f.getName()); continue; }
            String c = res.getDecompiledFunction().getC();
            String file = f.getEntryPoint().toString().replace(":", "") + "_" + f.getName() + ".c";
            PrintWriter pw = new PrintWriter(new FileWriter(new File(outdir, file)));
            pw.print(c); pw.close();
            idx.println(f.getEntryPoint() + "\t" + f.getName() + "\t" + file);
            n++;
        }
        idx.close();
        println("DECOMPILED " + n);
    }
}
