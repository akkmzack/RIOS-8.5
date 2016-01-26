#! /usr/bin/perl

# Find platform by looking for specific files.
# Some platforms have all the same nodes, but we don't really care

# SENS1: 1UOLD Rev A, DTAAA, DTAAB
# SENS2: 1UOLD Rev B, 1UAAA, 1UAAB

my $show_header = 0;

# Structure:
#   sensor, file, invert, invert_max
our $sysfs_sensors =
  {
   'SENS1' => [
               'TempCPU', '/sys/devices/platform/i2c-0/0-0290/temp1_input', 0, 0,
               'Temp2', '/sys/devices/platform/i2c-0/0-0290/temp2_input', 0, 0,
               'Temp3', '/sys/devices/platform/i2c-0/0-0290/temp3_input', 0, 0,
#               'Fan1', '/sys/devices/platform/i2c-0/0-0290/fan1_input', 0, 0,
#               'Fan2', '/sys/devices/platform/i2c-0/0-0290/fan2_input', 0, 0,
#               'Fan3', '/sys/devices/platform/i2c-0/0-0290/fan3_input', 0, 0,
              ],
   'SENS2' => [
#               'Fan1', '/sys/devices/platform/i2c-0/0-0000/fan1_input', 0, 0,
#               'Fan2', '/sys/devices/platform/i2c-0/0-0000/fan2_input', 0, 0,
               'TempCPU', '/sys/devices/platform/i2c-0/0-0000/temp1_input', 0, 0,
               'Temp2', '/sys/devices/platform/i2c-0/0-0000/temp2_input', 0, 0,
              ],
   '3UOLD-A' => [
                 'TempVRM', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/temp1_input', 0, 0,
                 'TempCPU1', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/temp2_input', 0, 0,
                 'TempCPU2', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/temp3_input', 0, 0,
                 'Temp1', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/temp1_input', 0, 0,
                 'Temp2', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/temp2_input', 0, 0,
                 'Temp3', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/temp3_input', 0, 0,
#                 'Fan1', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/fan1_input', 0, 0,
#                 'Fan2', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/fan2_input', 0, 0,
#                 'Fan3', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002a/fan3_input', 0, 0,
#                 'Fan4', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/fan1_input', 0, 0,
#                 'Fan5', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/fan2_input', 0, 0,
#                 'Fan6', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-0029/fan3_input', 0, 0,
                ],
   '3UOLD-B' => [
                 'TempCPU1', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/temp1_input', 0, 0,
                 'TempCPU2', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/temp2_input', 0, 0,
                 'Temp3', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/temp3_input', 0, 0,
                 'Temp4', '/sys/devices/platform/i2c-0/0-0290/temp1_input', 0, 0,
                 'Temp5', '/sys/devices/platform/i2c-0/0-0290/temp2_input', 0, 0,
                 'Temp6', '/sys/devices/platform/i2c-0/0-0290/temp3_input', 0, 0,
#                 'Fan1', '/sys/devices/platform/i2c-0/0-0290/fan1_input', 0, 0,
#                 'Fan2', '/sys/devices/platform/i2c-0/0-0290/fan2_input', 0, 0,
#                 'Fan3', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/fan1_input', 0, 0,
#                 'Fan4', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/fan2_input', 0, 0,
#                 'Fan5', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/fan3_input', 0, 0,
#                 'Fan6', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-1/1-002e/fan4_input', 0, 0,
                ],
   '3UAAA' => [
               'TempCPU', '/sys/devices/platform/i2c-0/0-0290/temp1_input', 0, 0,
               'Temp2', '/sys/devices/platform/i2c-0/0-0290/temp2_input', 0, 0,
               'Temp3', '/sys/devices/platform/i2c-0/0-0290/temp3_input', 0, 0,
#               'Fan0', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan0_input', 0, 0,
#               'Fan1', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan1_input', 0, 0,
#               'Fan2', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan2_input', 0, 0,
#               'Fan3', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan3_input', 0, 0,
#               'Fan4', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan4_input', 0, 0,
#               'Fan5', '/sys/devices/pci0000:00/0000:00:07.2/i2c-1/1-002c/fan5_input', 0, 0,
              ],
   'DTABA' => [
	       'TempCore0', '/proc/core_temp/0', 0, 0,
	       'TempCore1', '/proc/core_temp/1', 0, 0,
               'TempCPU', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/temp1_input', 0, 0,
               'TempSIO', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/temp2_input', 0, 0,
               'TempLAN', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/temp3_input', 0, 0,
#               'Fan1', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/fan1_input', 0, 0,
#               'Fan2', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/fan2_input', 0, 0,
#               'Fan3', '/sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/fan3_input', 0, 0,
              ],
   '1UABA' => [
               'TempCPU0', '/sys/devices/platform/i2c-1/1-0000/temp1_input', 1, 100,
               'TempCPU1', '/sys/devices/platform/i2c-1/1-0000/temp2_input', 1, 100,
               'TempSB', '/sys/devices/platform/i2c-1/1-0000/temp3_input', 0, 0,
               'TempMem', '/sys/devices/platform/i2c-1/1-0000/temp4_input', 0, 0,
               'TempLAN', '/sys/devices/platform/i2c-1/1-0000/temp5_input', 0, 0,
               'TempMCH', '/sys/devices/platform/i2c-1/1-0000/temp6_input', 0, 0,
               'TempBP1', '/sys/devices/platform/i2c-1/1-0000/temp7_input', 0, 0,
               'TempBP2', '/sys/devices/platform/i2c-1/1-0000/temp8_input', 0, 0,
               'TempPSU', '/sys/devices/platform/i2c-1/1-0000/temp9_input', 0, 0,
               'TempSys', '/sys/devices/platform/i2c-1/1-0000/temp10_input', 0, 0,
               'TempPS0', '/sys/devices/platform/i2c-1/1-0000/temp11_input', 0, 0,
               'TempPS1', '/sys/devices/platform/i2c-1/1-0000/temp12_input', 0, 0,
#               'Fan1', '/sys/devices/platform/i2c-1/1-0000/fan1_input', 0, 0,
#               'Fan3', '/sys/devices/platform/i2c-1/1-0000/fan2_input', 0, 0,
#               'Fan5', '/sys/devices/platform/i2c-1/1-0000/fan3_input', 0, 0,
#               'Fan6', '/sys/devices/platform/i2c-1/1-0000/fan4_input', 0, 0,
#               'Fan7', '/sys/devices/platform/i2c-1/1-0000/fan5_input', 0, 0,
#               'Fan8', '/sys/devices/platform/i2c-1/1-0000/fan6_input', 0, 0,
#               'Fan9', '/sys/devices/platform/i2c-1/1-0000/fan7_input', 0, 0,
#               'Fan10', '/sys/devices/platform/i2c-1/1-0000/fan8_input', 0, 0,
#               'Fan2', '/sys/devices/platform/i2c-1/1-0000/fan9_input', 0, 0,
#               'Fan4', '/sys/devices/platform/i2c-1/1-0000/fan10_input', 0, 0,
#	       'FanPS01', '/sys/devices/platform/i2c-1/1-0000/fan11_input', 0, 0,
#	       'FanPS02', '/sys/devices/platform/i2c-1/1-0000/fan12_input', 0, 0,
#	       'FanPS11', '/sys/devices/platform/i2c-1/1-0000/fan13_input', 0, 0,
#	       'FanPS12', '/sys/devices/platform/i2c-1/1-0000/fan14_input', 0, 0,
              ],
   '3UABA' => [
               'Temp1', '/sys/devices/platform/i2c-4/4-0000/temp1_input', 0, 0,
               'Temp2', '/sys/devices/platform/i2c-4/4-0000/temp2_input', 0, 0,
               'Temp3', '/sys/devices/platform/i2c-4/4-0000/temp3_input', 0, 0,
               'Temp4', '/sys/devices/platform/i2c-4/4-0000/temp4_input', 0, 0,
               'Temp5', '/sys/devices/platform/i2c-4/4-0000/temp5_input', 0, 0,
               'Temp6', '/sys/devices/platform/i2c-4/4-0000/temp6_input', 0, 0,
               'Temp7', '/sys/devices/platform/i2c-4/4-0000/temp7_input', 0, 0,
               'Temp8', '/sys/devices/platform/i2c-4/4-0000/temp8_input', 0, 0,
               'Temp9', '/sys/devices/platform/i2c-4/4-0000/temp9_input', 0, 0,
               'Temp10', '/sys/devices/platform/i2c-4/4-0000/temp10_input', 0, 0,
               'Temp11', '/sys/devices/platform/i2c-4/4-0000/temp11_input', 0, 0,
               'Temp12', '/sys/devices/platform/i2c-4/4-0000/temp12_input', 0, 0,
               'Temp13', '/sys/devices/platform/i2c-4/4-0000/temp13_input', 0, 0,
               'Temp14', '/sys/devices/platform/i2c-4/4-0000/temp14_input', 0, 0,
               'Temp15', '/sys/devices/platform/i2c-4/4-0000/temp15_input', 0, 0,
               'Temp16', '/sys/devices/platform/i2c-4/4-0000/temp16_input', 0, 0,
#               'Fan1', '/sys/devices/platform/i2c-4/4-0000/fan1_input', 0, 0,
#               'Fan2', '/sys/devices/platform/i2c-4/4-0000/fan2_input', 0, 0,
#               'Fan3', '/sys/devices/platform/i2c-4/4-0000/fan3_input', 0, 0,
#               'Fan4', '/sys/devices/platform/i2c-4/4-0000/fan4_input', 0, 0,
#               'Fan5', '/sys/devices/platform/i2c-4/4-0000/fan5_input', 0, 0,
#               'Fan6', '/sys/devices/platform/i2c-4/4-0000/fan6_input', 0, 0,
#               'Fan7', '/sys/devices/platform/i2c-4/4-0000/fan7_input', 0, 0,
#               'Fan8', '/sys/devices/platform/i2c-4/4-0000/fan8_input', 0, 0,
#               'Fan9', '/sys/devices/platform/i2c-4/4-0000/fan9_input', 0, 0,
#               'Fan10', '/sys/devices/platform/i2c-4/4-0000/fan10_input', 0, 0,
              ],
    'HPBLADE' => [
               'TempCore0', '/sys/devices/platform/coretemp.0/temp1_input', 0, 0,
               'TempCore1', '/sys/devices/platform/coretemp.1/temp1_input', 0, 0,
                 ],
  };

our $i2c_sensors = {
                    'DTABA' => [
                                'TempOutlet' => [0, 0x48],
                                'TempInlet'  => [0, 0x49],
                                'TempMICH'   => [0, 0x4a],
                                'TempDIMM'   => [0, 0x4b],
                               ]
                   };


$| = 1; # Enable autoflush

my $argc = 0;
while ($ARGV[$argc] =~ /^-/) {
    my $arg = $ARGV[$argc];
    if ($arg eq '--header') {
        $show_header = 1;
    } else {
	print "Usage: collect-temps.pl ?--header?\n";
	exit(1);
    }
    $argc++;
}

sub load_core_temp_module {
    my @locs = ('/lib/modules/2.6.9-34.EL-rbt-1705SMP/kernel/drivers/misc/core_temp.ko',
		'/var/tmp/core_temp.ko');
    foreach my $loc (@locs) {
	if (-f $loc) {
	    system("insmod $loc 2>/dev/null");
	    return;
	}
    }
}

sub what_sensor_platform {
    my $maxplatform = undef;
    my $maxcount = 0;
    foreach my $platform (keys %$sysfs_sensors) {
        my $count = 0;
        my @sensors = @{ $sysfs_sensors->{$platform} };
        while (@sensors) {
            my $sensor = shift @sensors;
            my $file = shift @sensors;
	    my $invert = shift @sensors;
	    my $invertmax = shift @sensors;
            #print "$sensor $file\n";
            if ( -f $file) {
                $count++;
            }
        }
        if ($count > $maxcount) {
            $maxcount = $count;
            $maxplatform = $platform;
        }
    }
    return $maxplatform;
}

load_core_temp_module;

our $PLATFORM = what_sensor_platform();
die "Could not figure our platform" unless $PLATFORM;
#print "Platform: $PLATFORM\n";
$i2c_sensors->{$PLATFORM} = [] unless exists $i2c_sensors->{$PLATFORM};

my $tempheader = '';
my $tempformat = '';
my $fanheader = '';
my $fanformat = '';
my @sensors = @{ $sysfs_sensors->{$PLATFORM} };
while (@sensors) {
    my $sensor = shift @sensors;
    my $file = shift @sensors;
    my $invert = shift @sensors;
    my $invertmax = shift @sensors;
    if (-f $file) {
	if ($sensor =~ /Temp/) {
	    if ($tempheader ne '') {
		$tempheader .= "\t";
		$tempformat .= "\t";
	    }
	    (my $v = $sensor) =~ s/Temp/T/;
	    $tempheader .= $v;
	    $tempformat .= "%d";
	} elsif ($sensor =~ /Fan/) {
	    $fanheader .= "\t$sensor";
	    $fanformat .= "\t%d";
	}
    }
}

@sensors = @{ $i2c_sensors->{$PLATFORM} };
while (@sensors) {
    my $sensor = shift @sensors;
    my $i2c_location = shift @sensors;
    if ($sensor =~ /Temp/) {
        if ($tempheader ne '') {
            $tempheader .= "\t";
            $tempformat .= "\t";
        }
        (my $v = $sensor) =~ s/Temp/T/;
        $tempheader .= $v;
        $tempformat .= "%d";
    }
}


our $HEADER = $tempheader . $fanheader . "\n";
our $FORMAT = $tempformat . $fanformat . "\n";

# ioctls
our $I2C_SLAVE       = 0x0703;
our $I2C_SMBUS       = 0x0720;

# operation type
our $I2C_SMBUS_READ  = 1;
our $I2C_SMBUS_WRITE = 0;

# sizes
our $I2C_SMBUS_BYTE  = 1;

#struct i2c_smbus_ioctl_data {
#        char read_write;
#        __u8 command;
#        int size;
#        union i2c_smbus_data *data;
#};

our $BUS  = 0;
our $device = "/dev/i2c-$BUS";
open(DEV, "+>", $device) || die "Unable to open $device: $!\n";

sub i2c_smbus_write_byte {
    my $value = shift;
    my $ign = 0;
    my $i2c_smbus_ioctl_data_t = "CCCCII";
    my $args = pack($i2c_smbus_ioctl_data_t,
                    $I2C_SMBUS_WRITE, $value, $ign, $ign, $I2C_SMBUS_BYTE, 0);
    return ioctl(DEV, $I2C_SMBUS, $args);
}

sub i2c_smbus_read_byte {
    my $ign = 0;
    my $i2c_smbus_ioctl_data_t = "CCCCIP";
    my $buf = ' ';
    my $args = pack($i2c_smbus_ioctl_data_t,
                    $I2C_SMBUS_READ, 0, $ign, $ign, $I2C_SMBUS_BYTE, $buf);
    if (!ioctl(DEV, $I2C_SMBUS, $args)) {
        return -1;
    }
    return unpack("C", $buf);
}

sub read_i2c {
    my $bus = shift;
    die if ($bus != $BUS);      # XXX/GCC: Ignore bus for now
    my $address = shift;
    ioctl(DEV, $I2C_SLAVE, $address);
    return i2c_smbus_read_byte();
}


sub read_temp_file {
    my $file = shift;
    open(F, $file) || die "Unable to open $file: $!\n";
    my $line = <F>;
    close(F);
    chomp($line);
    return eval($line) / 1000;
}

sub read_fan_file {
    my $file = shift;
    open(F, $file) || die "Unable to open $file: $!\n";
    my $line = <F>;
    close(F);
    chomp($line);
    return eval($line);
}

sub read_sensors {
    # Read the file based temps and fans
    my @sensors = @{ $sysfs_sensors->{$PLATFORM} };
    while (@sensors) {
        my $sensor = shift @sensors;
        my $file = shift @sensors;
	my $invert = shift @sensors;
	my $invertmax = shift @sensors;
	if (-f $file) {
	    if ($sensor =~ /Temp/) {
		my $temp = read_temp_file($file);
		if ($invert) {
		    $temp = $invertmax - $temp;
		}
		$temps{$sensor} = $temp;
		#print "sensor=$sensor, file=$file, temp=", $temps{$sensor}, "\n";
	    } elsif ($sensor =~ /Fan/) {
		$fans{$sensor} = read_fan_file($file);
		#print "sensor=$sensor, speed=", $fans{$sensor}, "\n";
	    }
	}
    }

    # Read the i2c based temps
    @sensors = @{ $i2c_sensors->{$PLATFORM} };
    while (@sensors) {
        my $sensor = shift @sensors;
        my $i2c_location = shift @sensors;
        my $bus = $i2c_location->[0];
        my $addr = $i2c_location->[1];
        $temps{$sensor} = read_i2c($bus, $addr);
        #print "sensor=$sensor, bus=$bus, addr=$addr, temp=", $temps{$sensor}, "\n";
    }
}

my $ts_header = '';
    #             2008-12-02 23:08:58
$ts_header = "Time               \t";

my $ts = `date '+%F %T'`;
chomp $ts;
$ts .= "\t";

if ($show_header) {
    print $ts_header.$HEADER;
}
read_sensors();

my @vals = ();
my @sensors = @{ $sysfs_sensors->{$PLATFORM} };
while (@sensors) {
    my $sensor = shift @sensors;
    my $file = shift @sensors;
    my $invert = shift @sensors;
    my $invertmax = shift @sensors;
    if (-f $file) {
        if ($sensor =~ /Temp/) {
            $vals[$#vals + 1] = $temps{$sensor};
        }
    }
}
@sensors = @{ $i2c_sensors->{$PLATFORM} };
while (@sensors) {
    my $sensor = shift @sensors;
    my $i2c_location = shift @sensors;
    if ($sensor =~ /Temp/) {
        $vals[$#vals + 1] = $temps{$sensor};
    }
}
@sensors = @{ $sysfs_sensors->{$PLATFORM} };
while (@sensors) {
    my $sensor = shift @sensors;
    my $file = shift @sensors;
    my $invert = shift @sensors;
    my $invertmax = shift @sensors;
    if (-f $file) {
        if ($sensor =~ /Fan/) {
            $vals[$#vals + 1] = $fans{$sensor};
        }
    }
}
printf($ts.$FORMAT, @vals);
exit(0);
