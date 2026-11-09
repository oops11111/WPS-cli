param([string]$In,[string]$Out,[int]$X,[int]$Y,[int]$W,[int]$H,[double]$Scale)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Bitmap]::FromFile($In)
$rect = New-Object System.Drawing.Rectangle($X,$Y,$W,$H)
$part = $src.Clone($rect, $src.PixelFormat)
$nw = [int]($W * $Scale); $nh = [int]($H * $Scale)
$bmp = New-Object System.Drawing.Bitmap($nw,$nh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$g.DrawImage($part, 0, 0, $nw, $nh)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose(); $part.Dispose(); $src.Dispose()