# PowerShell 7.5+. Run from any directory: pwsh -File contracts/verify.ps1
$ErrorActionPreference = 'Stop'

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-ContractJson([string]$RelativePath) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot $RelativePath) -Raw
}

function Assert-Result($Result) {
    $participantIds = @($Result.participants | ForEach-Object { $_.id })
    $segmentIds = @($Result.segments | ForEach-Object { $_.id })
    $taskIds = @($Result.tasks | ForEach-Object { $_.id })
    foreach ($ids in @(@{v=$participantIds}, @{v=$segmentIds}, @{v=$taskIds})) {
        Assert-True (@($ids.v | Select-Object -Unique).Count -eq $ids.v.Count) 'Duplicate ID'
    }
    $mapped = @($Result.participants | ForEach-Object { $_.speaker_ids })
    Assert-True (@($mapped | Select-Object -Unique).Count -eq $mapped.Count) 'Speaker mapped twice'
    $speakers = @($Result.segments | ForEach-Object { $_.speaker_id })
    foreach ($speaker in $mapped) {
        Assert-True ($speakers -contains $speaker) 'Mapped speaker does not exist'
    }
    $previousStart = -1.0
    foreach ($segment in $Result.segments) {
        Assert-True ($segment.start -ge 0 -and $segment.end -gt $segment.start) 'Invalid interval'
        Assert-True ($segment.start -ge $previousStart) 'Segments out of order'
        $previousStart = $segment.start
    }
    foreach ($task in $Result.tasks) {
        Assert-True ($null -eq $task.assignee_id -or $participantIds -contains $task.assignee_id) 'Unknown assignee'
        Assert-True ($task.source_segment_ids.Count -gt 0) 'Missing evidence'
        foreach ($source in $task.source_segment_ids) {
            Assert-True ($segmentIds -contains $source) 'Unknown evidence segment'
        }
        if ($null -eq $task.assignee_id -or $null -eq $task.due_date) {
            Assert-True ($task.needs_review -eq $true) 'Unknown information must be reviewed'
        }
        if ($null -ne $task.due_date) {
            $date = [datetime]::ParseExact($task.due_date, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture)
            Assert-True ($date.ToString('yyyy-MM-dd') -eq $task.due_date) 'Invalid due date'
        }
    }
}

$inputJson = Read-ContractJson 'examples/input.json'
$resultJson = Read-ContractJson 'examples/result.json'
$inputSchema = Join-Path $PSScriptRoot 'input.schema.json'
$resultSchema = Join-Path $PSScriptRoot 'result.schema.json'
Assert-True (Test-Json -Json $inputJson -SchemaFile $inputSchema) 'Input schema failed'
Assert-True (Test-Json -Json $resultJson -SchemaFile $resultSchema) 'Result schema failed'
$inputData = ConvertFrom-Json -InputObject $inputJson -DateKind String
$result = ConvertFrom-Json -InputObject $resultJson -DateKind String
foreach ($key in @('meeting_id', 'meeting_datetime', 'timezone')) {
    Assert-True ($inputData.$key -eq $result.$key) "Mismatched $key"
}
$meetingTime = [datetimeoffset]::Parse($inputData.meeting_datetime, [cultureinfo]::InvariantCulture)
$zone = [TimeZoneInfo]::FindSystemTimeZoneById($inputData.timezone)
Assert-True ($zone.GetUtcOffset($meetingTime) -eq $meetingTime.Offset) 'Timezone offset mismatch'
Assert-Result $result
Assert-True ($result.tasks[0].due_date -eq $meetingTime.AddDays(1).ToString('yyyy-MM-dd')) 'Tomorrow resolved incorrectly'
Assert-True ($result.tasks[0].assignee_id -eq 'p2') 'Cross-speaker assignment incorrect'
Assert-True (@($result.tasks | Where-Object { $_.source_segment_ids -contains 's3' }).Count -eq 0) 'Informational statement became a task'
Assert-True ($result.warnings[0].StartsWith('TEST_FIXTURE:')) 'Fixture label missing'

$negativeCases = @(
    @{name='unknown assignee'; mutate={param($r) $r.tasks[0].assignee_id='missing'}},
    @{name='unknown evidence'; mutate={param($r) $r.tasks[0].source_segment_ids=@('missing')}},
    @{name='duplicate ID'; mutate={param($r) $r.segments[1].id=$r.segments[0].id}},
    @{name='reversed interval'; mutate={param($r) $r.segments[0].end=-1}},
    @{name='invalid calendar date'; mutate={param($r) $r.tasks[0].due_date='2026-02-30'}},
    @{name='unreviewed unknown'; mutate={param($r) $r.tasks[1].needs_review=$false}}
)
foreach ($case in $negativeCases) {
    $bad = ConvertFrom-Json -InputObject $resultJson -DateKind String
    & $case.mutate $bad
    $rejected = $false
    try { Assert-Result $bad } catch { $rejected = $true }
    Assert-True $rejected "Negative case accepted: $($case.name)"
}
Write-Output 'PASS: input/result schemas, references, dates, fixture semantics; 6 invalid variants rejected.'
Write-Output 'This validates contracts only. No audio, models, application or DOCX was tested.'
