# Generate reference ISF streams with Microsoft.Ink (Win7 GAC assembly).
# Requires the Win7 image's Microsoft.Ink.dll (x86) extracted locally.
# Usage: powershell -File gen_reference_isf.ps1 -Out out.bin -Strokes 1 -Points 4 -Color 255 -Width 5 -Comp NoCompression
param(
  [Parameter(Mandatory=$true)][string]$Out,
  [int]$Strokes=1, [int]$Points=4, [int]$Color=0, [int]$Width=0,
  [string]$Comp='NoCompression',
  [string]$InkAsm=(Join-Path $PSScriptRoot '..\extracted\win7\mink32\Microsoft.Ink.dll')
)
[void][Reflection.Assembly]::LoadFrom($InkAsm)
Add-Type -AssemblyName System.Drawing
$ink = New-Object Microsoft.Ink.Ink
for ($s=0; $s -lt $Strokes; $s++) {
  $pts = New-Object 'System.Drawing.Point[]' $Points
  for ($i=0; $i -lt $Points; $i++) { $pts[$i] = New-Object System.Drawing.Point((100+$s*50+$i*10), (100+$i*7)) }
  $st = $ink.CreateStroke($pts)
  if ($Color -ne 0) { $st.DrawingAttributes.Color = [System.Drawing.Color]::FromArgb(0, (($Color -shr 16) -band 255), (($Color -shr 8) -band 255), ($Color -band 255)) }
  if ($Width -ne 0) { $st.DrawingAttributes.Width = $Width }
}
$a = [Reflection.Assembly]::LoadFrom($InkAsm)
$t = $a.GetType('Microsoft.Ink.Ink')
$pf = $a.GetType('Microsoft.Ink.PersistenceFormat')
$cm = $a.GetType('Microsoft.Ink.CompressionMode')
$m = $t.GetMethod('Save', [type[]]@($pf, $cm))
$b = $m.Invoke($ink, @([Enum]::Parse($pf,'InkSerializedFormat'), [Enum]::Parse($cm,$Comp)))
[IO.File]::WriteAllBytes($Out, $b)
Write-Output ('wrote {0} bytes' -f $b.Length)
