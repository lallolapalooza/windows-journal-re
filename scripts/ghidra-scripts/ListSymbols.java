//@category JNT.RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
public class ListSymbols extends GhidraScript {
    public void run() throws Exception {
        String pat = getScriptArgs()[0].toLowerCase();
        int n = 0;
        for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(true)) {
            if (s.getName().toLowerCase().contains(pat)) { println(s.getAddress() + " " + s.getSymbolType() + " " + s.getName()); n++; if (n > 200) break; }
        }
        println("TOTAL " + n);
    }
}
