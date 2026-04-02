<#
.SYNOPSIS
    Inspect the SAP GUI element tree via COM Scripting API for UiPath SAP selector generation.

.DESCRIPTION
    Connects to a running SAP GUI session via the SAP Scripting API (COM) and walks the
    control tree using a VBScript bridge. Outputs SAP-specific element data with properties
    that map directly to UiPath SAP selectors (<sap id='...' />).

    Features:
    - SAP COM Scripting API connection via VBScript bridge
    - Toolbar button probing (system tbar[0] and application tbar[1])
    - BFS walk of user area with container recursion
    - GuiTableControl detection with full column metadata and row-0 sample
    - Status bar capture
    - SAP type to UiPath activity mapping
    - Dynpro volatility warnings

    SAP Selector Pattern:
      <wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='...' />
      <sap id='usr/sub.../txtFIELD_NAME' />

    Prerequisites:
      1. Enable SAP Scripting: transaction RZ11 > sapgui/user_scripting = TRUE
      2. SAP GUI Options > Accessibility & Scripting > Enable scripting
      3. UiPath: Install UiPath.SAP.BAPI activities package
      4. Use 'SAP App' container activity or record SAP actions via UI Explorer

.PARAMETER WindowTitle
    Title (or wildcard pattern) of the SAP GUI window.
.PARAMETER WindowClass
    ClassName of the SAP window (typically 'SAP_FRONTEND_SESSION').
.PARAMETER ProcessName
    Process name to match. Defaults to 'saplogon.exe'.
.PARAMETER MaxElements
    Maximum number of SAP controls to output. Default: 300.
.PARAMETER OutputFormat
    'tree' (indented hierarchy), 'flat' (pipe-delimited), 'selectors' (UiPath selector XML),
    or 'json' (structured JSON for programmatic consumption). Default: selectors.
.EXAMPLE
    .\inspect-sap-tree.ps1 -WindowTitle "Create Purchase Order" -OutputFormat selectors
    .\inspect-sap-tree.ps1 -ProcessName "saplogon.exe" -OutputFormat tree
    .\inspect-sap-tree.ps1 -WindowTitle "*ME21N*" -OutputFormat json
#>
param(
    [string]$WindowTitle = "",
    [string]$WindowClass = "",
    [string]$ProcessName = "saplogon.exe",
    [int]$MaxElements = 300,
    [ValidateSet("tree", "flat", "selectors", "json")]
    [string]$OutputFormat = "selectors"
)

# ═══════════════════════════════════════════════════════════════════════════
# FIND TARGET WINDOW
# ═══════════════════════════════════════════════════════════════════════════

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$targetWindow = $null
$allWindows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)

$procNameCache = @{}
if ($ProcessName) {
    foreach ($w in $allWindows) {
        $pid2 = $w.Current.ProcessId
        if (-not $procNameCache.ContainsKey($pid2)) {
            $p = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
            $procNameCache[$pid2] = if ($p) { "$($p.ProcessName).exe" } else { "" }
        }
    }
}

foreach ($w in $allWindows) {
    $matchT = if ($WindowTitle) { $w.Current.Name -like $WindowTitle } else { $true }
    $matchC = if ($WindowClass) { $w.Current.ClassName -eq $WindowClass } else { $true }
    $matchP = if ($ProcessName) {
        $pn = $procNameCache[$w.Current.ProcessId]
        $pn -like $ProcessName
    } else { $true }
    if ($matchT -and $matchC -and $matchP) { $targetWindow = $w; break }
}
if (-not $targetWindow) {
    Write-Error "Window not found. Title='$WindowTitle' Class='$WindowClass' Process='$ProcessName'"
    Write-Output "Available windows:"
    foreach ($w in $allWindows) {
        $cn = $w.Current.ClassName; $nm = $w.Current.Name
        if ($nm -and $cn -notlike "Shell_*" -and $cn -ne "Progman") {
            $pid2 = $w.Current.ProcessId
            $pn = if ($procNameCache.ContainsKey($pid2)) { $procNameCache[$pid2] } else {
                $p = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
                if ($p) { "$($p.ProcessName).exe" } else { "?" }
            }
            Write-Output "  Title='$nm' | Class='$cn' | Process='$pn'"
        }
    }
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════
# SAP VALIDATION GATE
# ═══════════════════════════════════════════════════════════════════════════

$wc = $targetWindow.Current
$procId = $wc.ProcessId
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
$processName = if ($proc) { "$($proc.ProcessName).exe" } else { "unknown" }

$isSapGui = ($wc.ClassName -like 'SAP_*') -or ($processName -eq 'saplogon.exe')

if (-not $isSapGui) {
    Write-Error "Target window is NOT an SAP GUI application."
    Write-Output "  ClassName: $($wc.ClassName)"
    Write-Output "  ProcessName: $processName"
    Write-Output ""
    Write-Output "This script is designed exclusively for SAP GUI applications."
    Write-Output "For non-SAP apps, use inspect-ui-tree.ps1 instead."
    exit 1
}

$titleSel = $wc.Name
foreach ($sep in @(' - ', ' | ')) {
    if ($titleSel -match [regex]::Escape($sep)) {
        $appPart = ($titleSel -split [regex]::Escape($sep))[-1].Trim()
        $titleSel = "*$sep$appPart"; break
    }
}

$wndSel = "<wnd app='$($processName.ToLower())' cls='$($wc.ClassName)' title='$titleSel' />"

Write-Output "=== SAP GUI INSPECTION ==="
Write-Output ""
Write-Output "Window:"
Write-Output "  Title         = $($wc.Name)"
Write-Output "  ClassName     = $($wc.ClassName)"
Write-Output "  ProcessName   = $processName"
Write-Output ""
Write-Output "UiPath Window Selector:  $wndSel"
Write-Output ""

$script:jsonElements = @()

# ═══════════════════════════════════════════════════════════════════════════
# SAP COM SCRIPTING API VIA VBSCRIPT BRIDGE
# ═══════════════════════════════════════════════════════════════════════════

Write-Output "Connecting to SAP Scripting API via COM..."

$vbsTmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.vbs'
$outTmp = [System.IO.Path]::GetTempFileName()

$vbsCode = @'
On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    WScript.Echo "ERR_CONNECT|Cannot get SAPGUI object: " & Err.Description
    WScript.Quit 1
End If
Set application = SapGuiAuto.GetScriptingEngine
If Not IsObject(application) Then
    WScript.Echo "ERR_CONNECT|Cannot get scripting engine"
    WScript.Quit 1
End If
Set connection = application.Children(0)
Set session = connection.Children(0)

WScript.Echo "META|" & session.Info.Transaction & "|" & session.Info.SystemName & "|" & session.ActiveWindow.Text

' Walk toolbars via direct findById probing (Children enum unreliable for toolbars)
WScript.Echo "SECTION|tbar[0]|System Toolbar"
Dim tbi, tbb, ttxt, ttip
For tbi = 0 To 50
    Set tbb = session.FindById("wnd[0]/tbar[0]/btn[" & tbi & "]")
    If Err.Number = 0 Then
        ttxt = "" : ttip = ""
        ttxt = tbb.Text : If Err.Number <> 0 Then ttxt = "" : Err.Clear
        ttip = tbb.Tooltip : If Err.Number <> 0 Then ttip = "" : Err.Clear
        WScript.Echo "TBAR|0|" & tbi & "|" & ttxt & "|" & ttip
    Else
        Err.Clear
    End If
Next

WScript.Echo "SECTION|tbar[1]|Application Toolbar"
For tbi = 0 To 50
    Set tbb = session.FindById("wnd[0]/tbar[1]/btn[" & tbi & "]")
    If Err.Number = 0 Then
        ttxt = "" : ttip = ""
        ttxt = tbb.Text : If Err.Number <> 0 Then ttxt = "" : Err.Clear
        ttip = tbb.Tooltip : If Err.Number <> 0 Then ttip = "" : Err.Clear
        WScript.Echo "TBAR|1|" & tbi & "|" & ttxt & "|" & ttip
    Else
        Err.Clear
    End If
Next

' Recursive flat walk of user area - queue-based BFS
WScript.Echo "SECTION|usr|User Area"

Dim queue(500)
Dim qHead, qTail, maxEl, elCount
Dim curPath, curEl, cc, ci, cch
Dim eType, eName, eText, eChg, eId, eTip, eAA, eKids, skipTypes

qHead = 0 : qTail = 0
queue(qTail) = "wnd[0]/usr" : qTail = qTail + 1
maxEl = 300
elCount = 0

Do While qHead < qTail And elCount < maxEl
    curPath = queue(qHead) : qHead = qHead + 1

    Set curEl = session.FindById(curPath)
    If Err.Number <> 0 Then
        Err.Clear
    Else
        cc = curEl.Children.Count
        If Err.Number <> 0 Then cc = 0 : Err.Clear

        For ci = 0 To cc - 1
            If elCount >= maxEl Then Exit For
            Set cch = curEl.Children(CInt(ci))
            If Err.Number <> 0 Then
                Err.Clear
            Else
                eType = cch.Type : If Err.Number <> 0 Then eType = "?" : Err.Clear
                eName = cch.Name : If Err.Number <> 0 Then eName = "" : Err.Clear
                eText = Replace(Replace(cch.Text, vbCr, ""), vbLf, " ") : If Err.Number <> 0 Then eText = "" : Err.Clear
                eChg = cch.Changeable : If Err.Number <> 0 Then eChg = "" : Err.Clear
                eId = cch.Id : If Err.Number <> 0 Then eId = "" : Err.Clear
                eTip = cch.Tooltip : If Err.Number <> 0 Then eTip = "" : Err.Clear
                eAA = cch.AccTooltip : If Err.Number <> 0 Then eAA = "" : Err.Clear
                eKids = 0 : eKids = cch.Children.Count : If Err.Number <> 0 Then eKids = 0 : Err.Clear

                ' TABLE DETECTION: emit column metadata + row 0 sample, skip cell recursion
                If eType = "GuiTableControl" Then
                    Dim tblId, tblRows, tblVisRows, tblCols
                    tblId = eId : If Err.Number <> 0 Then tblId = "" : Err.Clear
                    tblRows = cch.RowCount : If Err.Number <> 0 Then tblRows = 0 : Err.Clear
                    tblVisRows = cch.VisibleRowCount : If Err.Number <> 0 Then tblVisRows = 0 : Err.Clear
                    tblCols = cch.Columns.Count : If Err.Number <> 0 Then tblCols = 0 : Err.Clear
                    WScript.Echo "TABLE_META|" & tblId & "|" & tblRows & "|" & tblVisRows & "|" & tblCols

                    Dim tci, tcol, tcName2, tcTip2, tcTitle2
                    Dim tCell, tCellType, tCellName, tCellText
                    For tci = 0 To tblCols - 1
                        tcName2 = "" : tcTip2 = "" : tcTitle2 = ""
                        tCellType = "" : tCellName = "" : tCellText = ""
                        Set tcol = cch.Columns.Item(CInt(tci))
                        If Err.Number <> 0 Then
                            Err.Clear
                        Else
                            tcName2 = tcol.Name : If Err.Number <> 0 Then tcName2 = "" : Err.Clear
                            tcTip2 = tcol.Tooltip : If Err.Number <> 0 Then tcTip2 = "" : Err.Clear
                            tcTitle2 = tcol.Title : If Err.Number <> 0 Then tcTitle2 = "" : Err.Clear
                        End If
                        Set tCell = cch.GetCell(0, CInt(tci))
                        If Err.Number = 0 Then
                            tCellType = tCell.Type : If Err.Number <> 0 Then tCellType = "" : Err.Clear
                            tCellName = tCell.Name : If Err.Number <> 0 Then tCellName = "" : Err.Clear
                            tCellText = tCell.Text : If Err.Number <> 0 Then tCellText = "" : Err.Clear
                        Else
                            Err.Clear
                        End If
                        WScript.Echo "TABLE_COL|" & tci & "|" & tcName2 & "|" & tcTip2 & "|" & tcTitle2 & "|" & tCellType & "|" & tCellName & "|" & Left(tCellText, 40)
                    Next
                    elCount = elCount + 1
                    ' DO NOT queue table children - avoids cell explosion
                Else
                    WScript.Echo "EL|" & eType & "|" & eName & "|" & Left(eText,80) & "|" & eChg & "|" & eId & "|" & Left(eTip,60) & "|" & Left(eAA,60) & "|" & eKids
                    elCount = elCount + 1

                    ' Queue containers for BFS (skip shells)
                    If eKids > 0 And qTail < 500 Then
                            skipTypes = "GuiShell"
                        If InStr(skipTypes, eType) = 0 Then
                            queue(qTail) = eId : qTail = qTail + 1
                        End If
                    End If
                End If
            End If
        Next
    End If
Loop

WScript.Echo "SECTION|sbar|Status Bar"
Dim sb
Set sb = session.FindById("wnd[0]/sbar")
If Err.Number = 0 Then
    Dim sbMsgType, sbText
    sbMsgType = sb.MessageType : If Err.Number <> 0 Then sbMsgType = "" : Err.Clear
    sbText = sb.Text : If Err.Number <> 0 Then sbText = "" : Err.Clear
    WScript.Echo "EL|GuiStatusbar|sbar|" & sbText & "|False|/app/con[0]/ses[0]/wnd[0]/sbar/pane[0]|" & sbMsgType & "||0"
    If Err.Number <> 0 Then Err.Clear
End If

WScript.Echo "DONE|" & elCount
'@

Set-Content -Path $vbsTmp -Value $vbsCode -Encoding ASCII

$cscript = Join-Path $env:SystemRoot "System32\cscript.exe"
$sapProc = Start-Process -FilePath $cscript -ArgumentList "//nologo `"$vbsTmp`"" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $outTmp -RedirectStandardError ([System.IO.Path]::GetTempFileName())

if ($sapProc.ExitCode -ne 0 -or -not (Test-Path $outTmp)) {
    Write-Output ""
    Write-Output "  SAP Scripting connection FAILED (exit code: $($sapProc.ExitCode))"
    Write-Output ""
    Write-Output "Troubleshooting checklist:"
    Write-Output "  1. Transaction RZ11 > parameter 'sapgui/user_scripting' must be TRUE"
    Write-Output "  2. SAP GUI Options > Accessibility & Scripting > Enable scripting must be checked"
    Write-Output "  3. Close and reopen the SAP transaction after enabling scripting"
    Write-Output "  4. Ensure only one SAP GUI session is connected (script uses Children(0))"
    Write-Output "  5. Run this script from an elevated PowerShell if COM access is blocked"
    Write-Output ""
    Write-Output "Note: Standard UI Automation (UIA) cannot see SAP GUI form fields, tables,"
    Write-Output "  or interactive elements. The SAP Scripting API is the only reliable method."
    Remove-Item $vbsTmp -ErrorAction SilentlyContinue
    Remove-Item $outTmp -ErrorAction SilentlyContinue
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════
# PARSE SAP TREE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════

$sapLines = Get-Content $outTmp

# Parse META line
$meta = $sapLines | Where-Object { $_ -match '^META\|' } | Select-Object -First 1
if ($meta) {
    $mp = $meta -split '\|'
    Write-Output "  Transaction: $($mp[1]) | System: $($mp[2])"
    Write-Output ""
}

# SAP type to UiPath activity mapping
$sapActivityMap = @{
    'GuiTextField'       = 'Type Into / Get Text'
    'GuiCTextField'      = 'Type Into / Get Text'
    'GuiPasswordField'   = 'Type Into (Secure)'
    'GuiComboBox'        = 'Select Item'
    'GuiButton'          = 'Click'
    'GuiLabel'           = 'Get Text'
    'GuiCheckBox'        = 'Check / Uncheck'
    'GuiRadioButton'     = 'Select'
    'GuiTab'             = 'Click (Select Tab)'
    'GuiTableControl'    = 'For Each Row / Get Cell'
    'GuiShell'           = 'Click / Select Cell (ALV Grid)'
    'GuiStatusbar'       = 'Get Text (Status)'
    'GuiToolbar'         = '(container)'
    'GuiSimpleContainer' = '(container)'
    'GuiCustomControl'   = '(container)'
    'GuiContainerShell'  = '(container)'
}

$currentSection = ""
$sapCount = 0
$currentTblId = ""

foreach ($line in $sapLines) {
    if ($line -match '^SECTION\|(.+)\|(.+)$') {
        Write-Output ""
        Write-Output "--- $($Matches[2]) [$($Matches[1])] ---"
        continue
    }

    # TOOLBAR BUTTONS: tbar[n]/btn[m] format
    if ($line -match '^TBAR\|') {
        $parts = $line -split '\|', 5
        $tbarIdx = $parts[1]
        $btnIdx  = $parts[2]
        $btnText = $parts[3]
        $btnTip  = $parts[4]

        $label = if ($btnTip) { $btnTip } elseif ($btnText) { $btnText } else { "btn[$btnIdx]" }

        if ($OutputFormat -eq 'selectors') {
            Write-Output ""
            Write-Output "# $label (Button)"
            Write-Output "$wndSel"
            $sapSel = "<sap id='tbar[$tbarIdx]/btn[$btnIdx]'"
            if ($btnTip) { $sapSel += " tooltip='$btnTip'" }
            $sapSel += " />"
            Write-Output "$sapSel"
            Write-Output "# Activity: Click"
        } elseif ($OutputFormat -eq 'tree') {
            $tipStr = if ($btnTip) { " tip='$btnTip'" } else { '' }
            Write-Output "  Button | tbar[$tbarIdx]/btn[$btnIdx] | $btnText |$tipStr"
        } elseif ($OutputFormat -eq 'json') {
            $script:jsonElements += @{
                controlType = 'GuiButton'; sapId = "tbar[$tbarIdx]/btn[$btnIdx]"
                text = $btnText; tooltip = $btnTip
                activityHint = 'Click'; section = "tbar[$tbarIdx]"
            }
        } else {
            Write-Output "Button|tbar[$tbarIdx]/btn[$btnIdx]|$btnText|E|tbar[$tbarIdx]/btn[$btnIdx]|$btnTip||0"
        }
        $sapCount++
        continue
    }

    # TABLE METADATA
    if ($line -match '^TABLE_META\|') {
        $parts = $line -split '\|', 5
        $tblFullId = $parts[1]
        $tblRows   = $parts[2]
        $tblVis    = $parts[3]
        $tblColCnt = $parts[4]
        $currentTblId = $tblFullId -replace '^/app/con\[\d+\]/ses\[\d+\]/wnd\[\d+\]/', ''

        if ($OutputFormat -eq 'selectors') {
            Write-Output ""
            Write-Output "# === TABLE: $($currentTblId -replace '.*/', '') ==="
            Write-Output "# Rows: $tblRows (visible: $tblVis) | Columns: $tblColCnt"
            Write-Output "# Base selector (use tableRow/tableCol or colTooltip to address cells):"
            Write-Output "$wndSel"
            Write-Output "<sap id='$currentTblId' tableRow='{row}' tableCol='{col}' />"
            Write-Output "# Or by column tooltip:"
            Write-Output "# <sap colTooltip='{tooltip}' id='$currentTblId' tableRow='{row}' />"
            Write-Output "# Activity: For Each Row / Get Cell / Set Cell"
            Write-Output ""
            Write-Output "# Column mapping:"
        } elseif ($OutputFormat -eq 'tree') {
            Write-Output "  TableControl | $($currentTblId -replace '.*/', '') | rows=$tblRows vis=$tblVis cols=$tblColCnt | [E]"
        } elseif ($OutputFormat -eq 'json') {
            $script:jsonElements += @{
                controlType = 'GuiTableControl'; sapId = $currentTblId
                rows = [int]$tblRows; visibleRows = [int]$tblVis
                columns = [int]$tblColCnt; isTable = $true
                activityHint = 'For Each Row / Get Cell'
                columnMapping = @()
            }
        }
        $sapCount++
        continue
    }

    # TABLE COLUMN
    if ($line -match '^TABLE_COL\|') {
        $parts = $line -split '\|', 8
        $colIdx    = $parts[1]
        $colName   = $parts[2]
        $colTip    = $parts[3]
        $colTitle  = $parts[4]
        $cellType  = $parts[5]
        $cellName  = $parts[6]
        $cellText  = $parts[7]

        $shortCellType = $cellType -replace '^Gui', ''
        $activity = switch ($cellType) {
            'GuiTextField'   { 'Type Into / Get Text' }
            'GuiCTextField'  { 'Type Into / Get Text' }
            'GuiButton'      { 'Click' }
            'GuiCheckBox'    { 'Check / Uncheck' }
            'GuiComboBox'    { 'Select Item' }
            default          { 'Get Text' }
        }

        if ($OutputFormat -eq 'selectors') {
            Write-Output "#   col $colIdx | $colTip | field=$cellName | type=$shortCellType | $activity"
        } elseif ($OutputFormat -eq 'tree') {
            Write-Output "    Col[$colIdx] $colTip ($colTitle) | $shortCellType $cellName"
        } elseif ($OutputFormat -eq 'json') {
            $lastTbl = $script:jsonElements | Where-Object { $_.isTable -eq $true } | Select-Object -Last 1
            if ($lastTbl) {
                $lastTbl.columnMapping += @{
                    index = [int]$colIdx; name = $colName; tooltip = $colTip
                    title = $colTitle; cellType = $shortCellType
                    fieldName = $cellName; activityHint = $activity
                }
            }
        } else {
            Write-Output "TableCol|$colIdx|$cellName|E|$currentTblId|$colTip|$colTitle|$shortCellType"
        }
        continue
    }

    # REGULAR ELEMENTS
    if ($line -match '^EL\|') {
        $parts = $line -split '\|', 9
        $elType  = $parts[1]
        $elName  = $parts[2]
        $elText  = $parts[3]
        $elChg   = $parts[4]
        $elId    = $parts[5]
        $elTip   = $parts[6]
        $elAA    = $parts[7]
        $elKids  = $parts[8]

        $shortType = $elType -replace '^Gui', ''
        $isContainer = $shortType -in @('SimpleContainer','CustomControl','ContainerShell','UserArea')

        # Build SAP selector path (strip session prefix)
        $sapId = $elId -replace '^/app/con\[\d+\]/ses\[\d+\]/wnd\[\d+\]/', ''

        if ($OutputFormat -eq 'selectors' -and -not $isContainer) {
            $activity = if ($sapActivityMap.ContainsKey($elType)) { $sapActivityMap[$elType] } else { 'Click' }

            $label = if ($elText) { $elText.Trim() } elseif ($elTip) { $elTip } else { $elName }
            Write-Output ""
            Write-Output "# $label ($shortType)$(if($elChg -eq 'True'){' [editable]'})"
            Write-Output "$wndSel"
            $sapSel = "<sap id='$sapId'"
            $tipVal = if ($elTip) { $elTip } elseif ($elAA) { $elAA } else { '' }
            if ($tipVal) { $sapSel += " tooltip='$($tipVal.Trim())'" }
            $sapSel += " />"
            Write-Output "$sapSel"
            Write-Output "# Activity: $activity"

            $sapCount++
        } elseif ($OutputFormat -eq 'json' -and -not $isContainer) {
            $activity = if ($sapActivityMap.ContainsKey($elType)) { $sapActivityMap[$elType] } else { 'Click' }
            $tipVal = if ($elTip) { $elTip.Trim() } elseif ($elAA) { $elAA.Trim() } else { '' }
            $script:jsonElements += @{
                controlType = $elType; name = $elName; text = $elText
                sapId = $sapId; editable = ($elChg -eq 'True')
                tooltip = $tipVal; activityHint = $activity
            }
            $sapCount++
        } elseif ($OutputFormat -eq 'flat') {
            $chgFlag = if ($elChg -eq 'True') { 'E' } else { 'R' }
            $tipInfo = if ($elTip) { " tip='$elTip'" } else { '' }
            $aaInfo = if ($elAA) { " aa='$elAA'" } else { '' }
            Write-Output "$shortType|$elName|$elText|$chgFlag|$sapId$tipInfo$aaInfo"
            $sapCount++
        } elseif ($OutputFormat -eq 'tree') {
            $depth = ($sapId -split '/' ).Count - 1
            $indent = '  ' * [Math]::Min($depth, 6)
            $chgFlag = if ($elChg -eq 'True') { '[E]' } else { '' }
            $tipStr = if ($elTip) { " tip='$($elTip.Substring(0,[Math]::Min($elTip.Length,30)))'" } else { '' }
            Write-Output "$indent$shortType | $elName | $($elText.Substring(0,[Math]::Min($elText.Length,40))) | $chgFlag$tipStr"
            $sapCount++
        }
    }
    if ($line -match '^DONE\|(\d+)') {
        # done
    }
}

if ($OutputFormat -eq 'json') {
    @{
        window = @{ title = $wc.Name; className = $wc.ClassName; processName = $processName }
        framework = "SAP GUI (MFC + COM Scripting)"
        selectorPattern = "<wnd.../> + <sap id='...' />"
        windowSelector = $wndSel
        totalControls = $sapCount
        elements = $script:jsonElements
        notes = @(
            "Sub-container dynpro numbers may change when header/item sections are expanded/collapsed"
            "Field names (e.g., txtMEPO_TOPLINE-EBELN) and table IDs remain stable"
            "Toolbar button indices have gaps - they are SAP internal IDs, not positional"
        )
    } | ConvertTo-Json -Depth 6
} else {
    Write-Output ""
    Write-Output "=== Summary ==="
    Write-Output "Total SAP controls: $sapCount (via COM Scripting API)"
    Write-Output "Framework: SAP GUI (MFC + COM Scripting)"
    Write-Output "Selector pattern: <wnd.../> + <sap id='...' />"
    Write-Output "  Toolbar: <sap id='tbar[n]/btn[m]' />"
    Write-Output "  Table cells: <sap id='tblID' tableRow='n' tableCol='n' /> or colTooltip='...'"
    Write-Output "  Fields: <sap id='usr/sub.../txtFIELD-NAME' />"
    Write-Output ""
    Write-Output "NOTE: Sub-container dynpro numbers (e.g., subSUB0:SAPLMEGUI:0016) may"
    Write-Output "  change when header/item sections are expanded/collapsed. The field names"
    Write-Output "  (e.g., txtMEPO_TOPLINE-EBELN) and table IDs remain stable."
}

# Cleanup temp files
Remove-Item $vbsTmp -ErrorAction SilentlyContinue
Remove-Item $outTmp -ErrorAction SilentlyContinue
