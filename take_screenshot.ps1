Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$top = $screen.Bounds.Top
$left = $screen.Bounds.Left
$width = $screen.Bounds.Width
$height = $screen.Bounds.Height
$bitmap = New-Object System.Drawing.Bitmap -ArgumentList $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($left, $top, 0, 0, $bitmap.Size)
$bitmap.Save("c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\desktop_screenshot.png", [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
