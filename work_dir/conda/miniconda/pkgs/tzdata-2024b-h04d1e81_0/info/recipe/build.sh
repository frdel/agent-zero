make -e \
  DESTDIR=./build \
  USRDIR='' \
  install

mkdir -p "${PREFIX}/share"
mv ./build/share/zoneinfo "${PREFIX}/share/"
