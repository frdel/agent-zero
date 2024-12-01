### How to re-generate patches
```bash
old=v3.9.6
new=v3.10.0
git clone git@github.com:python/cpython && cd cpython
git reset --hard $old
for f in ../recipe/patches/*.patch; do
  git am $f;
done
head=$(git rev-parse HEAD)
git reset --hard $new
git cherry-pick $old...$head  # fix conflicts and make sure the editor doesn't add end of file line ending
git format-patch $new
wget https://raw.githubusercontent.com/AnacondaRecipes/aggregate/8e3ab044c92c090e2b8ad46d295446690e76f5e3/make-mixed-crlf-patch.py
for f in $(grep -Iir "\.bat\|\.vcxproj\|\.props" -l recipe/patches/); do
  python make-mixed-crlf-patch.py $f;
done
```
