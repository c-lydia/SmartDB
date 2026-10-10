#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p test/build
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -Icomponents/fusion_core/include components/fusion_core/fusion_core.c test/test_fusion.c \
  -lm -o test/build/test_fusion
test/build/test_fusion test/build/fused-demo.bmp
cc -std=c11 -Icomponents/mlx90640/include components/mlx90640/MLX90640_API.c \
  test/test_mlx_failure.c -lm -o test/build/test_mlx_failure
test/build/test_mlx_failure
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -Icomponents/fusion_core/include components/fusion_core/protection.c test/test_protection.c \
  -lm -o test/build/test_protection
test/build/test_protection
if [ ! -f managed_components/espressif__cjson/cJSON/cJSON.c ]; then
  echo 'Build a firmware target once to download the pinned cJSON dependency for the settings tests.' >&2
  exit 1
fi
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -Itest/stubs -Imain -Iconfig -Imanaged_components/espressif__cjson/cJSON \
  main/device_settings.c managed_components/espressif__cjson/cJSON/cJSON.c test/test_device_settings.c \
  -lm -o test/build/test_device_settings
test/build/test_device_settings
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -Itest/stubs -Imain -Icomponents/fusion_core/include -Imanaged_components/espressif__cjson/cJSON \
  main/cloud_control.c managed_components/espressif__cjson/cJSON/cJSON.c test/test_cloud_control.c \
  -lm -o test/build/test_cloud_control
test/build/test_cloud_control
python3 -m unittest discover -s test -p 'test_*.py'
