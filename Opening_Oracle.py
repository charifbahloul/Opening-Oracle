import concurrent.futures
import datetime
import io
import json
import os
import random
import time
import traceback
from decimal import Decimal
from threading import Lock

import chess
import chess.pgn
import cloudscraper
import requests
from bs4 import BeautifulSoup

lo = Lock()


def get_first_parameters():
    elo_from = int(input("From what elo should we search from? "))
    elo_to = int(input(
        "To what elo should we search to (try to have a range of around 100-200 points)? "))

    path_save = input("Where should we save the jsons? ")
    os.chdir(path_save)

    while True:
        game_type = input(
            "What game type should we search for (e.g. blitz, rapid, bullet)? ")
        if game_type in ['blitz', 'rapid', 'bullet']:
            break
        else:
            print("Invalid game type.")

    return elo_from, elo_to, path_save, game_type


class DownloadPGNs(object):
    def __init__(self, elo_from, elo_to, path_save, game_type='blitz'):
        self.elo_from = elo_from
        self.elo_to = elo_to
        self.game_type = game_type

        self.path_save = path_save
        self.path_games = os.path.join(
            self.path_save, "JSONS", "Multi-PGN Games", self.game_type)

    def download_usernames(self, by_country=False):
        self.all_usernames = []

        if by_country:
            # TOP 10 countries by population of masters.
            country_list = [('France', '52'), ('Germany', '54'), ('Hungary', '67'), ('India', '69'), ('Poland', '112'), (
                'Russia', '116'), ('Serbia', '231'), ('Spain', '163'), ('Ukraine', '141'), ('United States', '2')]
        else:
            country_list = [('All', '0')]

        for country in country_list:
            # Approx. 100 usernames/elo.
            for rating in range(self.elo_from, self.elo_to+1, 1):
                while True:
                    try:
                        scraper = cloudscraper.create_scraper()
                        if country[0] == 'All':
                            response = scraper.get(f'https://www.chess.com/members/search?rating_type={self.game_type}&rating_min={rating}&rating_max={rating}&coaches=0&streamers=0&titledMembers=0&sortBy=last_login_date', headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36'})
                        else:
                            response = scraper.get(f'https://www.chess.com/members/search?country={country[1]}&rating_type={self.game_type}&rating_min={rating}&rating_max={rating}&coaches=0&streamers=0&titledMembers=0&sortBy=last_login_date', headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36'})

                        soup = BeautifulSoup(response.text, "lxml")
                        all_usernames_of_level = soup.find_all(
                            "a", attrs={'class': 'members-list-username'})

                        for user in all_usernames_of_level:
                            self.all_usernames.append(
                                user.text[23:-21].lower())
                            print(user)

                        time.sleep(.5)
                        break  # To get out of while loop.

                    except:
                        print(
                            'Problem with:', f'https://www.chess.com/members/search?rating_type={self.game_type}&rating_min={rating}&rating_max={rating+1}&coaches=0&streamers=0&titledMembers=0&sortBy=last_login_date')
                        print(traceback.format_exc())
                        time.sleep(30)

            print("Finished this country:", country[0])

        # Remove duplicates.
        self.all_usernames = list(set(self.all_usernames))
        with open(os.path.join(self.path_save, "Usernames", self.game_type + "_names.txt"), 'w') as f:
            f.write(str(self.all_usernames))

        print(len(self.all_usernames), "usernames found.")

    def load_usernames(self):  # For backwards compatibility.
        with open(os.path.join(self.path_save, "Usernames", self.game_type + "_names.txt"), 'r') as f:
            self.all_usernames = eval(f.read())

        print(len(self.all_usernames), "usernames loaded.")

    def download_games(self, num_months=6):
        year, months = self.calc_dates(num_months=num_months, include_curr_month=True)
        print("Months:", months)

        # At 25 workers, you're downloading 500 users/min or 1000 pgns/min. Uses 16 MB/sec.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=25)
        for user in self.all_usernames:
            executor.submit(self.download_user, user, year, months)

        executor.shutdown(wait=True)

    def calc_dates(self, num_months=6, include_curr_month=True):
        year = str(datetime.datetime.now().year)
        months = []
        months_list = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        if datetime.datetime.now().month < 10:
            this_month = months_list.index("0" + str(datetime.datetime.now().month))
        else:
            this_month = months_list.index(str(datetime.datetime.now().month))

        for month_num in range(num_months):
            # Don't include current month because there won't be lots of games if it's early in the month.
            if not include_curr_month:
                month_num += 1

            month = ""
            months.append(months_list[(this_month-month_num)% 12])

        return year, months

    def download_user(self, user, start_year, months):
        global lo

        last_month = months[0]
        for month in months:
            if int(month) > int(last_month):
                start_year = str(int(start_year)-1)
            try:
                user_pgn = self.download_pgn(user, start_year, month)
                user_pgn = self.strip_user_pgn(user_pgn)

                with lo:
                    with open(self.path_games + "\\" + 'all_pgns.pgn', 'a') as pgn_file:
                        pgn_file.write(user_pgn)
            except:
                print(traceback.format_exc())
            
            last_month = month

        print(user, 'downloaded')

    def download_pgn(self, user, year, month):
        response = requests.get(
            f"https://api.chess.com/pub/player/{user}/games/{year}/{month}/pgn")

        return str(response.text)

    def strip_user_pgn(self, user_pgn):
        accepted_time = False
        accepted_elo = False
        accepted_type = False
        new_pgn = []

        for line in user_pgn.splitlines():
            if line.startswith('[Event'):  # New game.
                accepted_type = True
            elif line.startswith('[Variant'):  # Don't want any variants.
                accepted_type = False
            elif line.startswith('[TimeControl'):
                accepted_time = self.is_ok_time_control(line)

            elif line.startswith('[WhiteElo') and int(line[11:len(line)-2]) >= self.elo_from and int(line[11:len(line)-2]) <= self.elo_to:
                accepted_elo = True
            elif line.startswith('[BlackElo') and int(line[11:len(line)-2]) >= self.elo_from and int(line[11:len(line)-2]) <= self.elo_to:
                accepted_elo = True

            elif accepted_time and accepted_elo and accepted_type and line.startswith('1.'):
                stripped_pgn = self.delete_extra_parts_pgn(line)
                if stripped_pgn != 'invalid':
                    opening_pgn = self.keep_only_opening(stripped_pgn)
                    if opening_pgn != '':
                        new_pgn.append(opening_pgn)
                else:
                    print(line)
                accepted_time = False
                accepted_elo = False

        return '\n'.join(new_pgn)

    def is_ok_time_control(self, line):
        time_controls = {'bullet': (0, 180), 'blitz': (
            180, 600), 'rapid': (600, 3600)}

        plus_sign = line.find('+')
        # With increment.
        if plus_sign != -1 and int(line[14:plus_sign]) + int(line[plus_sign+1:len(line)-2])*60 >= time_controls[self.game_type][0] and int(line[14:plus_sign]) + int(line[plus_sign+1:len(line)-2])*60 < time_controls[self.game_type][1]:
            return True
        # Daily time controls are not a valid game type.
        elif line.find('/') != -1:
            return False
        # No increment
        elif plus_sign == -1 and int(line[14:len(line)-2]) >= time_controls[self.game_type][0] and int(line[14:len(line)-2]) < time_controls[self.game_type][1]:
            return True
        else:
            return False

    def delete_extra_parts_pgn(self, line):
        num_open_brackets = 0
        in_brackets = False
        stripped_down_s = ""

        if line[2] == '.':
            return "invalid"

        for i in range(len(line)):
            if line[i] == '{':
                num_open_brackets += 1
                in_brackets = True
            elif line[i] == '}':
                in_brackets = False
            elif not in_brackets and i > 1 and line[i] == '.' and line[i-1] == '.' and line[i-2] == '.':
                while stripped_down_s[len(stripped_down_s)-1] != ' ':
                    stripped_down_s = stripped_down_s[:-1]
                stripped_down_s = stripped_down_s[:-1]  # Remove that space.
            elif not in_brackets and not (not in_brackets and i > 0 and line[i] == ' ' and stripped_down_s[len(stripped_down_s)-1] == ' '):
                stripped_down_s += line[i]

    def keep_only_opening(self, line):
        split_line = line.split(' ')

        # If it's less than 8 moves, it's not really a game.
        if len(split_line) < 25:
            return ''
        else:  # Only keep first 8 moves and winner.
            split_line = split_line[:24] + split_line[-1:]

        # Remove move numbers (e.g. '1.')
        split_line = [x for x in split_line if not x.endswith('.')]

        final_line = ' '.join(split_line)
        return final_line

    def fix_all_pgns(self):
        # Threading leads to some newlines not being printed.
        with open(self.path_games + "\\" + 'all_pgns.pgn') as f:
            all_pgns = f.read()

        # Search for '0-11' or '1-01' or '1/21' in the file and if found, insert a '\n' before the last 1.
        all_pgns = all_pgns.replace('0-11', '0-1\n1')
        all_pgns = all_pgns.replace('1-01', '1-0\n1')
        all_pgns = all_pgns.replace('1/21', '1/2\n1')
        print("Finished replacing.")

        # Won't need this this time. Only for backwards compatibility.
        new_pgns = []
        for line in all_pgns:
            opening_pgn = self.keep_only_opening(line)
            if opening_pgn != '':
                new_pgns.append(opening_pgn)

            if random.randint(0, 100000) == 0:
                print(line)

        all_pgns = ''.join(all_pgns)

        # Save.
        with open(self.path_games + "\\" + 'all_pgns.pgn', 'w') as f:
            f.write(all_pgns)


class AnalyzePGNs(object):
    def __init__(self, path_save):
        self.path_save = path_save
        self.fen_store_w = {}
        self.fen_store_b = {}

    def analyzer(self, start_at=0):
        self.open_all_pgns()
        self.load_fen_store()
        print("Opened pgns.")

        for i, pgn in enumerate(self.all_pgns[start_at:]):
            i += start_at
            self.read_pgn(i, pgn)

        print("Removing outliers for white.")
        self.fen_store_w = self.remove_extra_stuff(self.fen_store_w)

        print("Removing outliers for black.")
        self.fen_store_b = self.remove_extra_stuff(self.fen_store_b)

        print("Now saving to files.")
        self.save_fen_store()

    def open_all_pgns(self):
        with open(os.path.join(self.path_save, 'all_pgns.pgn'), 'r') as f:
            self.all_pgns = f.readlines()

    def load_fen_store(self):
        if not os.path.exists(os.path.join(self.path_save, 'wins_per_opening_white_all.json')):
            print("Wins per opening doesn't exist yet. That's ok.")
            return
        with open(os.path.join(self.path_save, 'wins_per_opening_white_all.json'), 'r') as f:
            self.fen_store_w = json.load(f)
        with open(os.path.join(self.path_save, 'wins_per_opening_black_all.json'), 'r') as f:
            self.fen_store_b = json.load(f)

    def game_result(self, pgn, colour):
        game_result = pgn[-4:-1]
        # Black won.
        if game_result == "0-1" and colour == 'w' or game_result == "1-0" and colour == 'b':
            winner = 0
        # White won.
        elif game_result == "1-0" and colour == 'w' or game_result == "0-1" and colour == 'b':
            winner = 1
        elif game_result == "1/2":
            winner = 0.5
        else:
            print("Error in game result:", game_result, colour)
            return None

        return winner

    def read_pgn(self, i, pgn):
        winner_w = self.game_result(pgn, 'w')
        winner_b = self.game_result(pgn, 'b')
        if winner_w is None or winner_b is None:
            return
        # When using, always print as ***int*** to get true move num. If .5, it's black. If already .0, it's white.
        move_num = 0.5

        try:
            game = chess.pgn.read_game(io.StringIO(pgn))
        except:
            print("Error reading game:", i)
        board = game.board()

        for move in game.mainline_moves():
            try:
                board.push(move)
            except:  # Probably is a variant where the move is illegal.
                print("Error pushing move:", i, move, board.fen())
                return

            move_num += 0.5
            # Saves a lot of time copared to board.fen() and we don't need the extra.
            fen = board.board_fen()

            # Not something.5 means it's white.
            if int(str(move_num)[-1]) != 5:
                self.add_to_fen_store(fen, winner_w, 'w')
            else:  # It's black's turn.
                self.add_to_fen_store(fen, winner_b, 'b')

        if i % 1000 == 0:
            # 11.3 Million games takes about 10 hours.
            print(datetime.datetime.now(), i)
        if i % 500000 == 499999:
            print("Saving just in case.")
            self.save_fen_store()  # Just in case.

    def add_to_fen_store(self, fen, winner, side):
        if side == 'w':
            try:
                self.fen_store_w[fen][0] += 1
                self.fen_store_w[fen][1] += winner
            except KeyError:
                self.fen_store_w[fen] = [1, winner]
        else:
            try:
                self.fen_store_b[fen][0] += 1
                self.fen_store_b[fen][1] += winner
            except KeyError:
                self.fen_store_b[fen] = [1, winner]

    def remove_extra_stuff(self, fen_store):
        new_fen_store = {}
        for fen in fen_store.keys():
            if fen_store[fen][0] >= 3:  # At least 3 games played.
                new_fen_store[fen] = fen_store[fen]

        return new_fen_store

    def save_fen_store(self):
        with open(os.path.join(self.path_save, "wins_per_opening_white_all.json"), "w") as f:
            json.dump(self.fen_store_w, f,
                      indent=4, default=str)

        with open(os.path.join(self.path_save, "wins_per_opening_black_all.json"), "w") as f:
            json.dump(self.fen_store_b, f,
                      indent=4, default=str)


class SearchOpenings(object):
    def __init__(self, color, path_save):
        self.current_pgn = ""
        self.suggestion = None
        self.path_save = path_save
        self.color = color
        self.root = None

    def new_game(self):
        self.current_pgn = ""

        if self.root == None:  # Shouldn't happen if you're loading them at the beginning.
            self.open_tree()

        while True:
            if self.input_pgn() == 0:  # Not found.
                self.current_pgn = ""
                break

    def open_tree(self):
        if self.color == 'w':
            with open(self.path_save + '\\wins_per_opening_white_all.json', 'r') as f:
                self.root = json.load(f)
        else:
            with open(self.path_save + '\\wins_per_opening_black_all.json', 'r') as f:
                self.root = json.load(f)

    def input_pgn(self):
        add_to_pgn = input("Current PGN: " + self.current_pgn)
        add_to_pgn = self.clean_add_to_pgn(add_to_pgn)

        if add_to_pgn == 'n':  # New game.
            self.current_pgn = ""
            print("\n\n")
            return 0
        # Undo last move. It deletes the last space and the last move.
        elif add_to_pgn == 'u':
            self.current_pgn = ' '.join(self.current_pgn.split(' ')[:-2])
        elif add_to_pgn == 'a':  # Accept suggestion.
            if self.suggestion is None:
                print("No suggestion.")
                return
            self.current_pgn = self.suggestion
        elif add_to_pgn == 'r':  # Want more than one rank.
            rank = input("Rank: ")
            try:
                rank = int(rank)
            except:
                print("Invalid input.")
                return

            if self.find_operation(rank=rank) == 0:  # Not found.
                return 0
        else:
            if not self.validate_pgn(add_to_pgn):
                print("Invalid move.")
                return

            self.current_pgn += add_to_pgn
            if self.find_operation() == 0:  # Not found.
                return 0

        # If it's length 0, we don't want a space.
        if self.current_pgn != '' and add_to_pgn != 'r':
            self.current_pgn += " "

    def find_operation(self, rank=5):
        if not self.last_move_color(self.current_pgn):
            recorded_moves, board = self.next_fen_finder()
            if len(recorded_moves) == 0:  # Nothing found in database.
                print("Not found in database.\n\n")
                return 0
            # Use this unless user comments it out because this is the whole purpose of the program.
            sorted_moves = self.basic_sort_moves(recorded_moves)
            self.print_all_sugg(sorted_moves, board, rank)
        else:
            try:
                current_fen = self.pgn_to_fen().fen()
                current_fen = self.remove_trivial_parts_fen(current_fen)
                fen_stats = self.root[current_fen]
                self.print_sugg(self.current_pgn, fen_stats[0], fen_stats[1])
            except KeyError:
                print("Not found in database.")
                return 0

    def clean_add_to_pgn(self, string):
        while string.count('  ') > 0:
            string.replace("  ", ' ')
        if len(string) > 0 and string[-1] == ' ':
            string = string[:-1]

        return string

    def validate_pgn(self, add_to_pgn):
        if len(self.current_pgn) == 0:
            validation_board = chess.Board()
        else:
            validation_board = chess.Board()
            # We don't want the last space.
            for move in self.current_pgn.split(' ')[:-1]:
                validation_board.push_san(move)

        try:
            if len(add_to_pgn) > 0:
                for move in add_to_pgn.split(' '):
                    validation_board.push_san(move)
        except ValueError:
            return False

        return True

    def next_fen_finder(self):
        board = self.pgn_to_fen()

        possible_moves_fen = []
        for move in list(board.legal_moves):
            new_board = board.copy()
            new_board.push(move)

            possible_moves_fen.append(new_board.fen())

        recorded_moves = []
        for fen in possible_moves_fen:
            fen = self.remove_trivial_parts_fen(fen)
            try:
                fen_stats = self.root[fen]
                recorded_moves.append([fen, fen_stats[0], fen_stats[1]])
            except:
                pass

        return recorded_moves, board

    def last_move_color(self, string):
        if string == '':  # No moves yet.
            return (self.color == 'b')

        if string[-1] == ' ':
            string = string[:-1]
        num_moves = len(string.split(" "))
        if num_moves % 2 == 1:
            return (self.color == 'w')
        else:
            return (self.color == 'b')

    def add_trivial_parts_fen(self, fen):
        fen = fen.split()
        fen.extend([self.color, 'KQkq', '-', '0', '1'])
        fen = ' '.join(fen)  # Adding trivial parts of the fen.
        return fen

    def remove_trivial_parts_fen(self, fen):
        fen = fen.split()
        # Remove move number and moves since pawn move since we want to allow transpositions.
        fen = fen[0]
        return fen

    def pgn_to_fen(self):
        if self.current_pgn == "":  # First move for white.
            return chess.Board()
        game = chess.pgn.read_game(io.StringIO(self.current_pgn))
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)

        return board

    # Note that this doesn't add numbering to the moves.
    def fen_to_pgn(self, board, target_fen):
        for move in list(board.legal_moves):
            new_board = board.copy()
            new_board.push(move)
            if self.remove_trivial_parts_fen(new_board.fen()) == target_fen:
                # Delete that first space if self.current_pgn is nothing.
                if self.current_pgn == '':
                    new_pgn = board.san(move)
                # This is when you're asking for rank (not first time).
                elif self.current_pgn[-1] == ' ':
                    new_pgn = self.current_pgn + board.san(move)
                else:  # Normal case.
                    new_pgn = self.current_pgn + " " + board.san(move)

        return new_pgn

    def basic_sort_moves(self, recorded_moves):
        sum_moves = 0  # Delete this par.
        most_freq = 0
        for fen in recorded_moves:
            sum_moves += fen[1]  # Frequency.
            if fen[1] > most_freq:
                most_freq = fen[1]

        good_moves = []
        for fen in recorded_moves:
            if fen[1] >= 0.01 * sum_moves and fen[2]/fen[1] >= .35:
                good_moves.append(fen)

        good_moves.sort(key=lambda item: item[2]/item[1], reverse=True)
        return good_moves

    def print_all_sugg(self, recorded_moves, board, rank=5):
        rank_num = 1
        for fen in recorded_moves:
            # new_sugg = fen[0] + "   " + str(fen[1]) + "   " + str(fen[2])
            new_sugg = self.fen_to_pgn(board, fen[0])
            self.print_sugg(new_sugg, fen[1], fen[2])

            if rank_num == 1:  # If only one rank is needed, use that suggestion.
                self.suggestion = new_sugg

            if rank_num == rank:
                break
            rank_num += 1

    def print_sugg(self, pgn, games_played, wins):
        print(pgn, '   ', games_played, '   ', str(
            round(Decimal(wins)/Decimal(games_played)*100, 3)) + "%")


def main():
    while True:
        start_new = input("Is this the first time you run this script (y/n): ")
        if start_new not in ['y', 'n']:
            print("Please enter 'y' or 'n'.")
        else:
            break

    if start_new == 'y':
        elo_from, elo_to, path_save, game_type = get_first_parameters()

        pgn_downloader = DownloadPGNs(elo_from, elo_to, path_save, game_type)
        # pgn_downloader.load_usernames() # Only for backwards compatibility.
        pgn_downloader.download_usernames()
        pgn_downloader.download_games()
        pgn_downloader.fix_all_pgns()

        AnalyzePGNs(path_save).analyzer()

    else:
        # path_save = input("Where are the jsons saved? ")
        os.chdir(path_save)

    # path_save = r'C:\Users\shari\Desktop\Python\Current_Projects\Chess Analysis\Chess Analysis 6\JSONS\blitz'
    # os.chdir(path_save)

    # To make it quicker, once it's loaded, opening a new game doesn't need to open root again.
    white_openings = SearchOpenings('w', path_save)
    black_openings = SearchOpenings('b', path_save)

    while True:
        color = ''
        while color != 'w' and color != 'b':
            color = input("What color are you playing as (w/b): ")
            if color != 'w' and color != 'b':
                print("Invalid color.")

        if color == 'w':
            white_openings.new_game()
        else:
            black_openings.new_game()

def run_only():
    # path_save = r'C:\Users\shari\Desktop\Python\Current_Projects\Chess Analysis\Chess Analysis 6\JSONS\blitz'
    path_save = r'C:\Users\shari\Desktop\Python\Current_Projects\Chess Analysis\Chess Analysis 6\JSONS\rapid'
    os.chdir(path_save)

    # To make it quicker, once it's loaded, opening a new game doesn't need to open root again.
    white_openings = SearchOpenings('w', path_save)
    black_openings = SearchOpenings('b', path_save)

    while True:
        color = ''
        while color != 'w' and color != 'b':
            color = input("What color are you playing as (w/b): ")
            if color != 'w' and color != 'b':
                print("Invalid color.")

        if color == 'w':
            white_openings.new_game()
        else:
            black_openings.new_game()

if __name__ == "__main__":
    main()
    # run_only()
