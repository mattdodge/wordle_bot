from collections import Counter
from copy import copy, deepcopy
from dataclasses import dataclass, field
from enum import Enum
import logging
from random import choice
import re

log = logging.getLogger("bot")
# logging.basicConfig(level=logging.INFO)

with open('words') as f:
    ALL_WORDS = [w.strip() for w in f.readlines()]

class Status(Enum):
    miss = 0
    wrong_spot = 1
    correct = 2

@dataclass
class Knowns:
    # letters locked in a spot
    locked: list = field(default_factory=lambda: [None] * 5)
    # letters still needed
    needed: set = field(default_factory=set)
    # Letters that cannot be at these positions
    impossibles: list = field(default_factory=lambda: [set(), set(), set(), set(), set()])


def solve(simulate_answer=None):
    knowns = Knowns()
    guesses = 0
    wordlist = 'words'

    while True:
        valid = valid_words(knowns, wordlist=wordlist)
        if len(valid) == 0:
            if wordlist == 'words':
                log.warning("Not in short list, trying long list")
                wordlist = 'extended'
                continue
            else:
                log.error("I give up")
                break
        log.debug(f"{len(valid)} valid words remain")
        guess, is_best = get_next_guess(valid, knowns)
        guesses += 1
        certainty = round(1.0 / len(valid) * 100)
        print(f"{'Best ' if is_best else ''}Guess: {guess.upper()} ({certainty}% certain)")
        if simulate_answer:
            result = get_result(guess, simulate_answer)
            print(f"Result: {result}")
        else:
            result = gather_response()
        success = update_knowns(guess, result, knowns)
        if success:
            print(f"Oh yeah, {guesses} guesses")
            break
    return guesses

def update_knowns(guess, result, knowns):
    """ Given a result, update a set of knowns. Return True if we were right """
    if all([res == Status.correct for res in result]):
        return True
    for slot, ch, res in zip(range(5), guess, result):
        if res == Status.miss:
            for i in knowns.impossibles:
                i.add(ch)
        elif res == Status.wrong_spot:
            # It CANT be in this slot, but it MUST be in the other slots
            knowns.impossibles[slot].add(ch)
            knowns.needed.add(ch)
        elif res == Status.correct:
            # We know it for a fact now
            knowns.locked[slot] = ch
    return False

def get_result(guess, answer):
    """ Given a guess and a known answer, return what the result would be """
    out = [None] * 5
    others = ""
    # First build exat matches and totally wrongs
    for pos, ch_guess, ch_answer in zip(range(5), guess, answer):
        if ch_guess == ch_answer:
            out[pos] = Status.correct
        elif ch_guess not in answer:
            out[pos] = Status.miss
            others += ch_answer
        else:
            others += ch_answer

    for pos, ch_guess in enumerate(guess):
        if out[pos]:
            continue
        elif ch_guess in others:
            out[pos] = Status.wrong_spot
        else:
            out[pos] = Status.miss
    return out

def best_guess(guess_words, remaining_words, knowns):
    """ Given our knowns and remaining word list, find the best guess """
    guess = None
    best_worst_score = len(remaining_words) + 1
    best_total_score = len(remaining_words)**2
    for guess_word in guess_words:
        log.info(f"Trying {guess_word}")
        word_worst = 0
        word_total = 0
        for possible_answer in copy(remaining_words):
            log.debug(f"  Trying possible answer {possible_answer}")
            result = get_result(guess_word, possible_answer)
            log.debug(f"  Result: {result}")
            new_knowns = Knowns()
            new_knowns.locked = deepcopy(knowns.locked)
            new_knowns.needed = deepcopy(knowns.needed)
            new_knowns.impossibles = deepcopy(knowns.impossibles)
            if update_knowns(guess_word, result, new_knowns):
                length = 0
            else:
                new_valid = valid_words(new_knowns)
                length = len(new_valid)
            log.debug(f"  Total remaining words {length}")
            word_total += length
            word_worst = max(length, word_worst)
        if word_total < best_total_score:
            log.info(f"{guess_word} is better (Total: {word_total}, Worst: {word_worst})")
            guess = guess_word
            best_worst_score = word_worst
            best_total_score = word_total
        elif word_total == best_total_score and word_worst < best_worst_score:
            log.info(f"{guess_word} is better (Total: {word_total}, Worst: {word_worst})")
            guess = guess_word
            best_worst_score = word_worst
            best_total_score = word_total
    return guess

def valid_words(knowns, wordlist='words'):
    """ Given a list of possible chars, return a list of valid words """
    with open(wordlist) as f:
        all_words = [w.strip() for w in f.readlines()]
    rr = get_regex_from_knowns(knowns)
    log.debug("Checking regex " + rr)
    log.debug("And we need " + str(knowns.needed))
    rex = re.compile(rr)
    return [w for w in all_words if rex.match(w) and all([n in w for n in knowns.needed])]

def what_do_i_know(answer, *guesses):
    """ Given a knwon answer and some guesses, which words are left """
    k = Knowns()
    for guess in guesses:
        res = get_result(guess, answer)
        update_knowns(guess, res, k)
    return valid_words(k)

def get_next_guess(valid_words, knowns):
    if len(valid_words) < 50:
        # If we're this close, we can guess any of the remaning words
        return best_guess(ALL_WORDS, valid_words, knowns), True
    elif len(valid_words) < 500:
        # Limit our best guess selection to valid words
        return best_guess(valid_words, valid_words, knowns), True
    char_counts = Counter()
    for w in valid_words:
        for pos, ch in enumerate(w):
            if knowns.locked[pos] is None:
                char_counts.update([ch])

    word_scores = []
    for word in valid_words:
        score = 0
        for pos, ch in enumerate(word):
            if knowns.locked[pos]:
                continue
            if ch in knowns.needed:
                # Don't consider letters we already know we need
                continue
            if ch in word[:pos]:
                # If we've already seen this letter don't count it towards the score
                continue
            score += char_counts[ch]
        word_scores.append((score, word))

    top_1pct = sorted(word_scores, reverse=True)[:max(3, round(len(word_scores) * 0.01))]
    log.debug("Top 3 are {}".format([w[1] for w in top_1pct[:3]]))
    return choice(top_1pct)[1], False

def get_regex_from_knowns(knowns):
    out = r''
    for locked_ch, impossible in zip(knowns.locked, knowns.impossibles):
        if locked_ch:
            out += locked_ch
        elif len(impossible) == 0:
            out += '.'
        else:
            out += '[^' + "".join(impossible) + ']'
    return out


def gather_response():
    resp = input("What's the result? (_/?/!) ")
    match = re.match(r'^[!?_]{5}', resp)
    if not match:
        log.warning("Invalid response string, try again")
        return gather_response()
    RESPS = {
        '_': Status.miss,
        '?': Status.wrong_spot,
        '!': Status.correct,
    }
    return [RESPS[ch] for ch in resp]

def simulate():
    with open('words') as f:
        all_words = [w.strip() for w in f.readlines()]
    with open('results', 'w+') as f:
        for word in all_words:
            guesses = solve(word)
            f.write(f"{word}\t{guesses}\n")

def main():
    solve()

if __name__ == '__main__':
    main()
    pass
