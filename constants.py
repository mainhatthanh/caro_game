BOARD_SIZE = 15

EMPTY = 0
PLAYER = 1
AI = - 1

PATTERN_SCORES = {
    # 5 quân
    "FIVE": 1000000,    ## .MMMM.

    # 4 mạnh
    "OPEN_FOUR": 120000,         
    "SEMI_OPEN_FOUR": 15000,     # EMMMM. hoặc .MMMME hoặc #MMMM. hoặc .MMMM#
    "BROKEN_FOUR": 18000,        # .MMM.M. / .MM.MM. / .M.MMM.
    "SEMI_BROKEN_FOUR": 6000,

    # 3 mạnh
    "OPEN_THREE": 5000,           # .MMM.
    "BROKEN_THREE": 3500,         # .MM.M. / .M.MM.
    "SEMI_OPEN_THREE": 800,

    # 2
    "OPEN_TWO": 300,            # .MM.
    "BROKEN_TWO": 150,          # .MM.
    "SEMI_OPEN_TWO": 50,

    # 1
    "OPEN_ONE": 10
}