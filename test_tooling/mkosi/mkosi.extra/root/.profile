cd archinstall-git
rm -rf dist

uv build --no-build-isolation --wheel
uv pip install dist/*.whl --break-system-packages --system --no-build --no-deps