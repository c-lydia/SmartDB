# LED Blink API Reference: ESP-IDF edition

## GPIO: General Purpose Input Output

### `esp_err_t gpio_reset_pin(gpio_num_t gpio_num)`

Reset a GPIO to a certain state (select gpio function, enable pullup and disable input and output).

- Parameters:
  - `gpio_num` -- GPIO number.
- Returns:
  - ESP_OK Success
  - ESP_ERR_INVALID_ARG Parameter error

### `esp_err_t gpio_set_level(gpio_num_t gpio_num, uint32_t level)`

GPIO set output level.

> Note:
> This function is allowed to be executed when Cache is disabled within ISR context, by enabling CONFIG_GPIO_CTRL_FUNC_IN_IRAM

- Parameters:
  - `gpio_num` -- GPIO number. If you want to set the output level of e.g. GPIO16, gpio_num should be GPIO_NUM_16 (16);
  - `level` -- Output level. 0: low ; 1: high
- Returns:
  - ESP_OK Success
  - ESP_ERR_INVALID_ARG GPIO number error

### `esp_err_t gpio_set_direction(gpio_num_t gpio_num, gpio_mode_t mode)`

GPIO set direction. Configure GPIO mode,such as output_only,input_only,output_and_input

> Note:
> This function always overwrite all the current modes that have applied on the IO pin

- Parameters:
  - `gpio_num` -- Configure GPIO pins number, it should be GPIO number. If you want to set direction of e.g. GPIO16, gpio_num should be GPIO_NUM_16 (16);
  - `mode` -- GPIO direction
- Returns:
  - ESP_OK Success
  - ESP_ERR_INVALID_ARG GPIO error

## LED Strip (`led_strip`)

### Allocate LED Strip Object with RMT Backend

``` c
#define BLINK_GPIO 0

/// LED strip common configuration
led_strip_config_t strip_config = {
    .strip_gpio_num = BLINK_GPIO,  // The GPIO that connected to the LED strip's data line
    .max_leds = 1,                 // The number of LEDs in the strip,
    .led_model = LED_MODEL_WS2812, // LED strip model, it determines the bit timing
    .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB, // The color component format is G-R-B
    .flags = {
        .invert_out = false, // don't invert the output signal
    }
};

/// RMT backend specific configuration
led_strip_rmt_config_t rmt_config = {
    .clk_src = RMT_CLK_SRC_DEFAULT,    // different clock source can lead to different power consumption
    .resolution_hz = 10 * 1000 * 1000, // RMT counter clock frequency: 10MHz
    .mem_block_symbols = 64,           // the memory size of each RMT channel, in words (4 bytes)
    .flags = {
        .with_dma = false, // DMA feature is available on chips like ESP32-S3/P4
    }
};

/// Create the LED strip object
led_strip_handle_t led_strip = NULL;
ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &led_strip));
```

### Allocate LED Strip Object with SPI Backend

``` c
#define BLINK_GPIO 0

/// LED strip common configuration
led_strip_config_t strip_config = {
    .strip_gpio_num = BLINK_GPIO,  // The GPIO that connected to the LED strip's data line
    .max_leds = 1,                 // The number of LEDs in the strip,
    .led_model = LED_MODEL_WS2812, // LED strip model, it determines the bit timing
    .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB, // The color component format is G-R-B
    .flags = {
        .invert_out = false, // don't invert the output signal
    }
};

/// SPI backend specific configuration
led_strip_spi_config_t spi_config = {
    .clk_src = SPI_CLK_SRC_DEFAULT, // different clock source can lead to different power consumption
    .spi_bus = SPI2_HOST,           // SPI bus ID
    .flags = {
        .with_dma = true, // Using DMA can improve performance and help drive more LEDs
    }
};

/// Create the LED strip object
led_strip_handle_t led_strip = NULL;
ESP_ERROR_CHECK(led_strip_new_spi_device(&strip_config, &spi_config, &led_strip));
```

### function `led_strip_clear`

Clear LED strip (turn off all LEDs)

``` c
esp_err_t led_strip_clear (
    led_strip_handle_t strip
) 
```

- Parameters:
  - `strip` LED strip
- Returns:
  - ESP_OK: Clear LEDs successfully
  - ESP_FAIL: Clear LEDs failed because some other error occurred

### function `led_strip_refresh`

Refresh memory colors to LEDs.

``` c
esp_err_t led_strip_refresh (
    led_strip_handle_t strip
) 
```

- Parameters:
  - `strip` LED strip
- Returns:
  - ESP_OK: Refresh successfully
  - ESP_FAIL: Refresh failed because some other error occurred

> Note:
> After updating the LED colors in the memory, a following invocation of this API is needed to flush colors to strip.

### function `led_strip_set_pixel`

Set RGB for a specific pixel.

``` c
esp_err_t led_strip_set_pixel (
    led_strip_handle_t strip,
    uint32_t index,
    uint32_t red,
    uint32_t green,
    uint32_t blue
)
```

- Parameters:
  - `strip` LED strip
  - `index` index of pixel to set
  - `red` red part of color
  - `green` green part of color
  - `blue` blue part of color
- Returns:
  - ESP_OK: Set RGB for a specific pixel successfully
  - ESP_ERR_INVALID_ARG: Set RGB for a specific pixel failed because of invalid parameters
  - ESP_FAIL: Set RGB for a specific pixel failed because other error occurred

### struct `led_strip_rmt_config_t`

LED Strip RMT specific configuration.

- Variables:
  - `rmt_clock_source_t clk_src` RMT clock source
  - `struct led_strip_rmt_config_t::led_strip_rmt_extra_config flags` Extra driver flags
  - `size_t mem_block_symbols` How many RMT symbols can one RMT channel hold at one time. Set to 0 will fallback to use the default size. Extra RMT specific driver flags
  - `uint32_t resolution_hz` RMT tick resolution, if set to zero, a default resolution (10MHz) will be applied

### function `led_strip_new_rmt_device`

Create LED strip based on RMT TX channel.

``` c
esp_err_t led_strip_new_rmt_device (
    const led_strip_config_t *led_config,
    const led_strip_rmt_config_t *rmt_config,
    led_strip_handle_t *ret_strip
) 
```

- Parameters:
  - `led_config` LED strip configuration
  - `rmt_config` RMT specific configuration
  - `ret_strip` Returned LED strip handle
- Returns:
  - ESP_OK: create LED strip handle successfully
  - ESP_ERR_INVALID_ARG: create LED strip handle failed because of invalid argument
  - ESP_ERR_NO_MEM: create LED strip handle failed because of out of memory
  - ESP_FAIL: create LED strip handle failed because some other error

### struct `led_strip_spi_config_t`

LED Strip SPI specific configuration.

- Variables:
  - `spi_clock_source_t clk_src` SPI clock source
  - `struct led_strip_spi_config_t flags` Extra driver flags
  - `spi_host_device_t spi_bus` SPI bus ID. Which buses are available depends on the specific chip
  - `uint32_t with_dma` Use DMA to transmit data

### function `led_strip_new_spi_device`

Create LED strip based on SPI MOSI channel.

``` c
esp_err_t led_strip_new_spi_device (
    const led_strip_config_t *led_config,
    const led_strip_spi_config_t *spi_config,
    led_strip_handle_t *ret_strip
) 
```

> Note:
> Although only the MOSI line is used for generating the signal, the whole SPI bus can’t be used for other purposes.

- Parameters:
  - `led_config` LED strip configuration
  - `spi_config` SPI specific configuration
  - `ret_strip` Returned LED strip handle
- Returns:
  - ESP_OK: create LED strip handle successfully
  - ESP_ERR_INVALID_ARG: create LED strip handle failed because of invalid argument
  - ESP_ERR_NOT_SUPPORTED: create LED strip handle failed because of unsupported configuration
  - ESP_ERR_NO_MEM: create LED strip handle failed because of out of memory
  - ESP_FAIL: create LED strip handle failed because some other error
