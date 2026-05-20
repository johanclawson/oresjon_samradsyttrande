# Bygg PDF av yttranden via Pandoc + Eisvogel-mall.
#
# Använder MD som källa (efter add_links.py-bearbetning) så alla länkar finns
# med. Eisvogel ger professionell typografi, TOC, klickbara länkar och
# konsekvent layout.
#
# Användning:
#   .\scripts\build-pdf.ps1                  # Bygger alla yttranden
#   .\scripts\build-pdf.ps1 -Source yttranden\yttrande_kollektivt.md
#
# Förutsättningar (engångs):
#   - MiKTeX: winget install MiKTeX.MiKTeX
#   - Eisvogel-mall i %APPDATA%\pandoc\templates\ (laddas ned från
#     https://github.com/Wandmalfarbe/pandoc-latex-template/releases)

param(
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

# Lägg till MiKTeX och Pandoc i PATH om de inte redan finns.
$miktexPath = "C:\Users\johan\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
$pandocPath = "C:\Users\johan\AppData\Local\Pandoc"
foreach ($p in @($miktexPath, $pandocPath)) {
    if (Test-Path $p) {
        $env:PATH = "$p;$env:PATH"
    }
}

# Kontrollera beroenden.
try {
    $pandocVersion = & pandoc --version | Select-Object -First 1
    Write-Host "Pandoc: $pandocVersion" -ForegroundColor Green
} catch {
    Write-Host "Pandoc saknas" -ForegroundColor Red
    exit 1
}

try {
    & xelatex --version | Out-Null
    Write-Host "xelatex: OK" -ForegroundColor Green
} catch {
    Write-Host "xelatex saknas - installera MiKTeX: winget install MiKTeX.MiKTeX" -ForegroundColor Red
    exit 1
}

# Metadata per yttrandet (titel + valbar undertitel).
$metadata = @{
    "yttrande_kollektivt" = @{
        title    = "Förslag – kollektivt yttrande"
        subtitle = "Detaljplan PLAN.2024.747 (Ubbhult 2:2 / Håkankila 1:8, Sätila)"
        author   = "Undertecknande fastighetsägare"
        toc      = $true
    }
    "yttrande_vaghallarperspektiv" = @{
        title    = "Förslag – yttrande med väghållarperspektiv"
        subtitle = "Detaljplan PLAN.2024.747 – Lygnersvider ga:1"
        author   = "[Förvaltande samfällighetsförening för Lygnersvider ga:1]"
        toc      = $true
    }
    "anslutningsmail_mall" = @{
        title    = "Anslutningsmail till kollektivt yttrande"
        subtitle = "Detaljplan PLAN.2024.747 – mall för enskilda sakägare"
        author   = ""
        toc      = $false
    }
}

function Build-Pdf {
    param(
        [string]$MdPath
    )

    $base = [System.IO.Path]::GetFileNameWithoutExtension($MdPath)
    $pdfPath = [System.IO.Path]::ChangeExtension($MdPath, ".pdf")

    $meta = $metadata[$base]
    if (-not $meta) {
        Write-Host "  Hoppar över $base (ingen metadata definierad)" -ForegroundColor Yellow
        return $false
    }

    Write-Host "`nBygger PDF: $MdPath -> $pdfPath" -ForegroundColor Cyan
    Write-Host "  Titel: $($meta.title)" -ForegroundColor Gray
    if ($meta.subtitle) { Write-Host "  Undertitel: $($meta.subtitle)" -ForegroundColor Gray }

    $args = @(
        $MdPath,
        "-o", $pdfPath,
        "--template=eisvogel",
        "--pdf-engine=xelatex",
        "--resource-path=$projectDir",
        "--syntax-highlighting=tango",
        "-V", "titlepage=true",
        "-V", "titlepage-color=1A4A7A",
        "-V", "titlepage-text-color=FFFFFF",
        "-V", "titlepage-rule-color=FFFFFF",
        "-V", "titlepage-rule-height=2",
        "-V", "colorlinks=true",
        "-V", "linkcolor=[HTML]{1A4A7A}",
        "-V", "urlcolor=[HTML]{1A4A7A}",
        "-V", "toccolor=[HTML]{1A4A7A}",
        "-V", "table-use-row-colors=true",
        "-V", "geometry:margin=2.5cm",
        "-V", "mainfont=Calibri",
        "-V", "sansfont=Calibri",
        "-V", "monofont=Consolas",
        "-V", "fontsize=11pt",
        "-V", "lang=sv-SE",
        "-V", "title=$($meta.title)"
    )

    if ($meta.subtitle) { $args += @("-V", "subtitle=$($meta.subtitle)") }
    if ($meta.author) { $args += @("-V", "author=$($meta.author)") }
    if ($meta.toc) {
        $args += @("--toc", "--toc-depth=3", "-V", "toc-own-page=true")
    }

    & pandoc @args

    if ($LASTEXITCODE -eq 0 -and (Test-Path $pdfPath)) {
        $size = [math]::Round((Get-Item $pdfPath).Length / 1KB, 1)
        Write-Host "  OK ($size KB)" -ForegroundColor Green
    } else {
        Write-Host "  PDF-genereringen misslyckades" -ForegroundColor Red
        return $false
    }
    return $true
}

if ($Source) {
    # Specifik fil — bygger alltid (även om utanför metadata-listan),
    # användbart för lokala filer som inte är publika.
    $mdPath = Join-Path $projectDir $Source
    if (-not (Test-Path $mdPath)) {
        Write-Host "Filen finns inte: $mdPath" -ForegroundColor Red
        exit 1
    }
    $base = [System.IO.Path]::GetFileNameWithoutExtension($mdPath)
    if (-not $metadata[$base]) {
        # Lägg till generisk metadata för lokala filer.
        $metadata[$base] = @{
            title    = $base
            subtitle = ""
            author   = ""
            toc      = $true
        }
    }
    Build-Pdf -MdPath $mdPath | Out-Null
} else {
    # Bygger endast yttranden som finns i metadata-listan (publika).
    foreach ($base in $metadata.Keys) {
        $mdPath = Join-Path $projectDir "yttranden\$base.md"
        if (Test-Path $mdPath) {
            Build-Pdf -MdPath $mdPath | Out-Null
        }
    }
}

Write-Host "`nKlart." -ForegroundColor Green
