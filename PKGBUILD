# Maintainer: <you>

pkgname=pypaper
pkgver=0.1.0
pkgrel=1
pkgdesc='Wallpaper manager for Hyprland'
arch=('any')
url='https://github.com/lePelch/pypaper'
license=('unknown')
depends=('python' 'pyside6' 'hyprland' 'hyprpaper')
makedepends=('python-build' 'python-installer' 'python-hatchling')
source=()
sha256sums=()

build() {
  cd "$startdir"
  python -m build --wheel --no-isolation
}

package() {
  cd "$startdir"
  python -m installer --destdir="${pkgdir}" dist/*.whl
}
