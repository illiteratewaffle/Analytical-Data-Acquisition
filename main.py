from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError

board_num = 0
channel = 0
ai_range = ULRange.BIP5VOLTS

while(1 == 1):

    try:
        # Get a value from the device
        value = ul.a_in(board_num, channel, ai_range)
        # Convert the raw value to engineering units
        eng_units_value = ul.to_eng_units(board_num, ai_range, value)

        # Display the raw value
        print("Raw Value: " + str(value))
        # Display the engineering value
        print("Engineering Value: " + '{:.4f}'.format(eng_units_value))
    except ULError as e:
        # Display the error
        print("A UL error occurred. Code: " + str(e.errorcode)
              + " Message: " + e.message)