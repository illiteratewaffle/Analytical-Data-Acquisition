import nidaqmx

# Define your input channels
analog_inputs = ["Dev1/ai0", "Dev1/ai1"]

# Create a task to read voltage
with nidaqmx.Task() as ai_task:
    for ch in analog_inputs:
        ai_task.ai_channels.add_ai_voltage_chan(ch, min_val=-10.0, max_val=10.0)

    # Read one sample per channel
    voltages = ai_task.read()
    print(f"Read voltages from {analog_inputs}: {voltages}")


# Create the analog output task
ao_task = nidaqmx.Task()

# Add AO channels
ao_task.ao_channels.add_ao_voltage_chan("Dev1/ao0", min_val=0.0, max_val=5.0)
ao_task.ao_channels.add_ao_voltage_chan("Dev1/ao1", min_val=0.0, max_val=5.0)

# Set output voltages
voltages = [2.5, 1.0]  # volts for ao0 and ao1
ao_task.write(voltages, auto_start=True)

print(f"Set Dev1/ao0 to {voltages[0]} V and Dev1/ao1 to {voltages[1]} V")

# Clean up
ao_task.stop()
ao_task.close()

