from collections import Counter
from enum import Enum
import logging
from random import choice
import re

log = logging.getLogger("bot")
# logging.basicConfig(level=logging.DEBUG)

class Status(Enum):
    miss = 0
    wrong_spot = 1
    correct = 2

def solve(simulate_answer=None):
    # letters locked in a spot
    locked = [None] * 5
    # letters still needed
    needed = set()
    impossibles = [set(), set(), set(), set(), set()]
    guesses = 0
    wordlist = 'words'

    while True:
        valid = valid_words(locked, needed, impossibles, wordlist=wordlist)
        if len(valid) == 0:
            if wordlist == 'words':
                log.warning("Not in short list, trying long list")
                wordlist = 'extended'
                continue
            else:
                log.error("I give up")
                break
        log.debug(f"{len(valid)} valid words remain")
        guess = get_next_guess(valid, locked, needed)
        guesses += 1
        certainty = round(1.0 / len(valid) * 100)
        print(f"Guess: {guess.upper()} ({certainty}% certain)")
        if simulate_answer:
            result = get_result(guess, simulate_answer)
            print(f"Result: {result}")
        else:
            result = gather_response()
        if all([res == Status.correct for res in result]):
            print(f"Oh yeah, {guesses} guesses")
            break
        for slot, ch, res in zip(range(5), guess, result):
            if res == Status.miss:
                for i in impossibles:
                    i.add(ch)
            elif res == Status.wrong_spot:
                # It CANT be in this slot, but it MUST be in the other slots
                impossibles[slot].add(ch)
                needed.add(ch)
            elif res == Status.correct:
                # We know it for a fact now
                locked[slot] = ch
    return guesses

def get_result(guess, answer):
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

def valid_words(locked, needed, impossibles, wordlist='words'):
    """ Given a list of possible chars, return a list of valid words """
    with open(wordlist) as f:
        all_words = [w.strip() for w in f.readlines()]
    rr = get_regex_from_knowns(locked, impossibles)
    log.debug("Checking regex " + rr)
    log.debug("And we need " + str(needed))
    rex = re.compile(rr)
    return [w for w in all_words if rex.match(w) and all([n in w for n in needed])]

def get_next_guess(valid_words, locked, needed):
    char_counts = Counter()
    for w in valid_words:
        for pos, ch in enumerate(w):
            if locked[pos] is None:
                char_counts.update([ch])

    word_scores = []
    for word in valid_words:
        score = 0
        for pos, ch in enumerate(word):
            if locked[pos]:
                continue
            if ch in needed:
                # Don't consider letters we already know we need
                continue
            if ch in word[:pos]:
                # If we've already seen this letter don't count it towards the score
                continue
            score += char_counts[ch]
        word_scores.append((score, word))

    top_1pct = sorted(word_scores, reverse=True)[:max(3, round(len(word_scores) * 0.01))]
    log.debug("Top 3 are {}".format([w[1] for w in top_1pct[:3]]))
    return choice(top_1pct)[1]

def get_regex_from_knowns(locked, impossibles):
    out = r''
    for locked_ch, impossible in zip(locked, impossibles):
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
