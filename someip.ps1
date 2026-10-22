$ErrorActionPreference = 'Stop'
& python "$PSScriptRoot/scripts/kit.py" @args
exit $LASTEXITCODE
