param(
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    [string]$Kigumi = ".\experiments\kigumi\bin\kigumi.exe",
    [string]$Target = ".\cnc_boolean_target.stl",
    [string]$Cutter = ".\cnc_boolean_cutter.stl",
    [string]$Out = ".\cnc_kigumi_result.obj",
    [string]$Report = ".\cnc_kigumi_report.txt"
)

$ErrorActionPreference = "Stop"

foreach ($path in @($Blender, $Kigumi, $Target, $Cutter)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "File not found: $path"
    }
}

$Blender = (Resolve-Path -LiteralPath $Blender).Path
$Kigumi = (Resolve-Path -LiteralPath $Kigumi).Path
$Target = (Resolve-Path -LiteralPath $Target).Path
$Cutter = (Resolve-Path -LiteralPath $Cutter).Path
$Out = [IO.Path]::GetFullPath($Out)
$Report = [IO.Path]::GetFullPath($Report)

$targetObj = [IO.Path]::ChangeExtension($Out, ".target.obj")
$cutterObj = [IO.Path]::ChangeExtension($Out, ".cutter.obj")
$prepReport = [IO.Path]::ChangeExtension($Out, ".input-report.json")
$prepScript = Join-Path $PSScriptRoot "prepare_obj_inputs.py"

Write-Host "== 1/3: Convert exact STL operands to OBJ (no repair/reduction) =="
& $Blender -b --python $prepScript -- --target $Target --cutter $Cutter --target-obj $targetObj --cutter-obj $cutterObj --report $prepReport
if ($LASTEXITCODE -ne 0) { throw "Blender STL-to-OBJ conversion failed (exit $LASTEXITCODE)" }

Write-Host "== 2/3: Run Kigumi Difference =="
$env:KIGUMI_NUM_THREADS = [string][Environment]::ProcessorCount
$timer = [Diagnostics.Stopwatch]::StartNew()
$booleanOutput = & $Kigumi boolean --first $targetObj --second $cutterObj --dif $Out 2>&1
$booleanExit = $LASTEXITCODE
$timer.Stop()
$booleanOutput | Tee-Object -FilePath $Report
if ($booleanExit -ne 0) { throw "Kigumi Boolean failed (exit $booleanExit)" }
if (-not (Test-Path -LiteralPath $Out -PathType Leaf)) { throw "Kigumi did not create output: $Out" }

Write-Host "== 3/3: Check result topology =="
$checkOutput = & $Kigumi check --in $Out 2>&1
$checkExit = $LASTEXITCODE
$checkOutput | Tee-Object -FilePath $Report -Append
if ($checkExit -ne 0) { throw "Kigumi check failed (exit $checkExit)" }

Write-Host ""
Write-Host ("Kigumi Boolean elapsed: {0:N3} s" -f $timer.Elapsed.TotalSeconds)
Write-Host "Result OBJ: $Out"
Write-Host "Input conversion report: $prepReport"
Write-Host "Boolean and topology log: $Report"
Write-Host "Do not import the result into CNC PRO 3D until geometry and topology are reviewed."
