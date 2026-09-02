# Maintainer: Vikyek <https://github.com/Vikyek>
pkgname=toon-mcp
pkgver=1.0.0
pkgrel=1
pkgdesc="Pure Python FastMCP Server for Token-Optimized Object Notation (TOON) JSON payload compression"
arch=('any')
url="https://github.com/Vikyek/toon-mcp"
license=('MIT')
depends=('python' 'python-mcp' 'python-setuptools')
makedepends=('python-build' 'python-installer' 'python-wheel')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$pkgname-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
