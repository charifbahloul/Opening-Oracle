# Opening Oracle
Analysis of the best moves to play in the opening depending on your ELO on chess.com.

After inputting a range of ELOs and waiting for a while, you will be able to access the best openings in white and black for that range and the best moves within each opening to try.

This was developed because there are ***NO DATABASES FOR LOWER ELOS*** to find out what the best openings are in their ELO range to try. 

# Installation

- Download and extract source code.
- Install all dependencies:
    - Note that although there are specific versions listed for each dependency, future versions are most probably backwards-compatible (i.e. You can get away with dependencies with higher versions but not lower versions).
    - In addition, this program was built using Python 3.10.4. You can probably get away with anything higher than that.
- Run `Opening_Oracle.py`.
    - If you just want to play around with it, the dataset for 12M games @ 1200 blitz is included.
        - Input the pgn.
        - If it's your move, it'll give you the best move followed by the num. of games in the database (almost like a confidence level) and the win percentage if you play the move.
        - You can press:
            - `r` to view more suggestions.
            - `a` to accept a suggestion.
            - `u` to undo the last move (for one player). Can be pressed multiple times.
            - `n` to start a new game.
    - As noted below, it'll take a long time to download the data.

# Personal Story

Personally, I developed this because I have always struggled with openings. Although I'm adequate at middlegames and endgames, many of my games were being decided because of a losing position coming out of the opening. While there are databases for masters, they are exactly that; a database that shows the best openings for masters. Masters usually know all of the main openings and often don't fall for simple traps (e.g. Fried Liver Attack). However, us common folk do. Depending on one's ELO, one can use this program to find the best opening for their level. Everyone from 300-3000 ELO can use this program and start winning in chess.

# Easter eggs (for blitz 1200)
- For white, it's best to open with b4, which is supposedly one of the worst openings according to all the databases. But the "shock factor" outweighs the point loss (b4 @53.065% while f4 @ 52.906%).
- For black, the karo-kann is best (c6 @ 50.382% while e6 @ 49.805%).
- Optimally, white will win 53% of the time.
- 12 million games is the result of 77,000 usernames downloading the past 6 months of their games. Not including username collection (which takes at least 7 hours x 4 days because of some buggy cloudflare), it took about 7.5 hours to download usernames and 8 hours to analyze them. Good thing is that it runs automatically in the background.
- Etc.

# Limitations

- There is a point to be made that many of the traps in the lower ELOs are inconsistent; there will be players who fall for it and players who don't. However, picking semi-common openings will ensure that that doesn't happen often enough to make a difference.
- To ensure that there are enough games to work with, you must download at least a few million games. Otherwise, the accuracy will be bad and it won't show you anything for later moves. Unfortunately, this means that the time needed to run it the first time is extremely long. If there's a faster way to download and analyze millions of games, I'm all ears (see below).

# Suggestions, Contributions and Issues

Any and all contributions are welcome. If you have an issue, feel free to raise it in the issues tab. A great next step would be to use an engine as a sanity check so that some ridiculous moves that have a 90% chance of working don't lose the game if the opponent doesn't fall for it.