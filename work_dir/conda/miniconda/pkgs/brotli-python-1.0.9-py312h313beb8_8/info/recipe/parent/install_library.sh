ninja install

if [[ "${PKG_NAME}" == "libbrotlicommon" ]]; then
  rm -rf ${PREFIX}/bin/brotli
  rm -rf ${PREFIX}/lib/libbrotlidec*
  rm -rf ${PREFIX}/lib/libbrotlienc*
  rm -rf ${PREFIX}/lib/pkgconfig/libbrotli{enc,dec}.pc
elif [[ "${PKG_NAME}" == "libbrotlienc" ]]; then
  rm -rf ${PREFIX}/bin/brotli
  rm -rf ${PREFIX}/lib/libbrotlidec*
  rm -rf ${PREFIX}/lib/pkgconfig/libbrotlidec.pc
elif [[ "${PKG_NAME}" == "libbrotlidec" ]]; then
  rm -rf ${PREFIX}/bin/brotli
  rm -rf ${PREFIX}/lib/libbrotlienc*
  rm -rf ${PREFIX}/lib/pkgconfig/libbrotlienc.pc
fi

if [[ "${PKG_NAME}" != "brotli" ]]; then
  rm -rf ${PREFIX}/include/brotli
fi
