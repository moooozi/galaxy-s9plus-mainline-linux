// SPDX-License-Identifier: GPL-2.0
/* Publish decoded SSP samples using Linux IIO. Firmware/protocol ownership
 * stays with the single userspace SSP reader. No fabricated initial readings.
 */
#include <linux/fs.h>
#include <linux/iio/iio.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/uaccess.h>

struct sample { __le32 sensor; __le32 value[3]; };
struct sensor_state {
 struct iio_dev *indio;
 int value[3];
 bool registered;
};
static struct sensor_state sensors[3];
static DEFINE_MUTEX(sample_lock);
static DEFINE_MUTEX(publish_lock);
static atomic_t opened = ATOMIC_INIT(0);

static int sensor_read(struct iio_dev *indio, const struct iio_chan_spec *chan,
                       int *val, int *val2, long mask)
{
 struct sensor_state *s = *(struct sensor_state **)iio_priv(indio);
 if (mask == IIO_CHAN_INFO_SCALE) {
  /* Samsung SSP accelerometer: 4096 counts/g, IIO units m/s^2. */
  *val = 0;
  *val2 = 2394202;
  return IIO_VAL_INT_PLUS_NANO;
 }
 if (mask != IIO_CHAN_INFO_RAW && mask != IIO_CHAN_INFO_PROCESSED)
  return -EINVAL;
 mutex_lock(&sample_lock);
 *val = s->value[chan->address];
 mutex_unlock(&sample_lock);
 return IIO_VAL_INT;
}
static const struct iio_info sensor_info = { .read_raw = sensor_read };
#define AXIS(t, a, n, scale) { .type = t, .modified = 1, .channel2 = a, \
 .address = n, .info_mask_separate = BIT(IIO_CHAN_INFO_RAW), \
 .info_mask_shared_by_type = scale }
static const struct iio_chan_spec accel_channels[] = {
 AXIS(IIO_ACCEL, IIO_MOD_X, 0, BIT(IIO_CHAN_INFO_SCALE)),
 AXIS(IIO_ACCEL, IIO_MOD_Y, 1, BIT(IIO_CHAN_INFO_SCALE)),
 AXIS(IIO_ACCEL, IIO_MOD_Z, 2, BIT(IIO_CHAN_INFO_SCALE)),
};
/* Preserve gyro raw counts until its firmware range/scale is verified. */
static const struct iio_chan_spec gyro_channels[] = {
 AXIS(IIO_ANGL_VEL, IIO_MOD_X, 0, 0),
 AXIS(IIO_ANGL_VEL, IIO_MOD_Y, 1, 0),
 AXIS(IIO_ANGL_VEL, IIO_MOD_Z, 2, 0),
};
static const struct iio_chan_spec light_channels[] = {
 { .type = IIO_LIGHT, .info_mask_separate = BIT(IIO_CHAN_INFO_PROCESSED) },
};

static void remove_sensors(void)
{
 int i;
 for (i = 0; i < ARRAY_SIZE(sensors); i++) {
  if (sensors[i].registered)
   iio_device_unregister(sensors[i].indio);
  if (sensors[i].indio)
   iio_device_free(sensors[i].indio);
  sensors[i].indio = NULL;
  sensors[i].registered = false;
 }
}

static int samples_open(struct inode *inode, struct file *file)
{
 return atomic_cmpxchg(&opened, 0, 1) ? -EBUSY : 0;
}
static int samples_release(struct inode *inode, struct file *file)
{
 /* Removing devices makes SensorProxy discard values when the daemon dies. */
 remove_sensors();
 atomic_set(&opened, 0);
 return 0;
}
static ssize_t samples_write_locked(struct file *file, const char __user *buf,
                            size_t len, loff_t *pos)
{
 static const char *const names[] = { "s9plus-accel", "s9plus-gyro", "s9plus-light" };
 struct sample sample;
 struct sensor_state *s;
 unsigned int id, index;
 int i, ret;
 if (len != sizeof(sample))
  return -EINVAL;
 if (copy_from_user(&sample, buf, sizeof(sample)))
  return -EFAULT;
 id = le32_to_cpu(sample.sensor);
 if (id != 0 && id != 1 && id != 9)
  return -EINVAL;
 index = id == 9 ? 2 : id;
 s = &sensors[index];
 mutex_lock(&sample_lock);
 for (i = 0; i < 3; i++)
  s->value[i] = (s32)le32_to_cpu(sample.value[i]);
 mutex_unlock(&sample_lock);
 if (s->registered)
  return len;
 s->indio = iio_device_alloc(NULL, sizeof(s));
 if (!s->indio)
  return -ENOMEM;
 *(struct sensor_state **)iio_priv(s->indio) = s;
 s->indio->name = names[index];
 s->indio->info = &sensor_info;
 s->indio->modes = INDIO_DIRECT_MODE;
 s->indio->channels = index == 0 ? accel_channels : index == 1 ? gyro_channels : light_channels;
 s->indio->num_channels = index == 2 ? 1 : 3;
 ret = iio_device_register(s->indio);
 if (ret) {
  iio_device_free(s->indio);
  s->indio = NULL;
  return ret;
 }
 s->registered = true;
 return len;
}
static ssize_t samples_write(struct file *file, const char __user *buf,
                            size_t len, loff_t *pos)
{
 ssize_t ret;
 mutex_lock(&publish_lock);
 ret = samples_write_locked(file, buf, len, pos);
 mutex_unlock(&publish_lock);
 return ret;
}
static const struct file_operations samples_fops = {
 .owner = THIS_MODULE, .open = samples_open, .release = samples_release,
 .write = samples_write,
};
static struct miscdevice samples_misc = {
 .minor = MISC_DYNAMIC_MINOR, .name = "s9plus_sensor_samples",
 .fops = &samples_fops, .mode = 0600,
};
static int __init samples_init(void) { return misc_register(&samples_misc); }
static void __exit samples_exit(void) { misc_deregister(&samples_misc); }
module_init(samples_init);
module_exit(samples_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Galaxy S9+ decoded SSP samples as standard IIO devices");
