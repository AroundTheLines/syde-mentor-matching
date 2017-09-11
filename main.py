# Python standard library imports
import csv
import os
import re
from collections import defaultdict

# External Libraries
from sortedcontainers import SortedDict


def header_map(h):
    return {
        "Timestamp": "timestamp",
        "What is your name?": "name",
        "What is your email?": "email",
        "What is your gender?": "gender",
        "What class are you in": "class",
        "What gender would you prefer to mentor for?": "gender_mentee",
        "What do you feel comfortable/qualified giving advice for (select all that apply)": "advice",
        "What gender would you prefer to have as a mentor?": "gender_mentor",
        "What advice are you seeking (select all that apply)": "help",
        "What's your favorite pass time": "hobbies",
        "Tell me a bit about yourself": "description",
        "What's your favourite dad joke/pun?": "joke",
        "Are you excited for 1A/2B?": "excitement"
    }.get(h, h)


# Makes the data easier to work with.
def replace_headers(input_file):
    output_file = os.path.splitext(input_file)[0] + "_modified.csv"
    with open(input_file, "r", encoding="UTF-8") as in_f, open(output_file, "w", encoding="UTF-8") as o_f:
        reader = csv.reader(in_f)
        writer = csv.writer(o_f)

        headers = next(reader, None)
        writer.writerow(['id'] + [header_map(header) for header in headers] )
        for i, row in enumerate(reader):
            writer.writerow([i] + row)

    return output_file


def get_data(file_location):
    with open(file_location, "r", encoding="UTF-8") as csvfile:
        return [r for r in csv.DictReader(csvfile)]


def process_row(row):
    # SortedListWithKey keeps the list sorted according to a function I define (aka a heap)
    row["prefs"] = SortedDict()
    row["prefs_20"] = SortedDict()
    row["class"] = "2020" if row['class'] == "SYDE 2020" else "SYDE 2022"
    if row['advice']:
        row['advice'] = row['advice'].split(",")
    if row["help"]:
        row["help"] = row["help"].split(",")

    return row


# Gets 2020s and 2022s
def split_years(data):
    cls_20 = {}
    cls_22 = {}
    for row in data:
        row = process_row(row)
        if row['class'] == "2020":
            cls_20[row['id']] = row
        else:
            cls_22[row['id']] = row
    return cls_20, cls_22


def get_preferences(cls_20, cls_22):
    for up, up_data in cls_20.items():
        # get matching prefs with babysydes
        for low, low_data in cls_22.items():
            # Get the number of shared unique topics to chat about
            len_intersect = len(set(up_data['advice']).intersection(set(low_data['help'])))

            # Save match % to preferences
            cls_20[up]["prefs"][low] = (len_intersect / len(up_data['advice']))
            cls_22[low]["prefs"][up] = (len_intersect / len(low_data['help']))

    return cls_20, cls_22


def get_pairing_preferences(cls_20):
    for up, up_data in cls_20.items():
        # get matching prefs within class by maximizing amount of unique topics
        for up_2, up_data_2 in cls_20.items():
            if up == up_2:
                cls_20[up]["prefs_20"][up_2] = 0

            unique_topics = set(up_data['advice'] + up_data_2['advice'])
            cls_20[up]["prefs_20"][up_2] = len(unique_topics)
    return cls_20


def get_mentors(cls_20, cls_22):
    # defaultdict(...) is just a way saying that every key to the
    # dictionary will start with the result of the function in the parameters
    # ex: I'm using a lambda function to default it to a nested dictionary
    mentors = defaultdict(lambda: {})
    cls_22_free = list(cls_22.keys())

    # This deep copies the objects so pointers aren't pointing to the original object
    cls_20_copy = {k: v for k, v in cls_20.items()}
    cls_22_copy = {k: v for k, v in cls_22.items()}

    while cls_22_free:
        # tt = twenty two, tw = twenty
        tt = cls_22_free.pop(0)
        tt_mentors = cls_22_copy[tt]['prefs']

        tw = max(tt_mentors.items(), key=lambda x: x[1])[0] # get id of max with [0]
        tw_val = tt_mentors.pop(tw) # remove max from dict


        # grab a copy of the mentorship preferences from 2020 side
        tw_mentees = cls_20_copy[tw]['prefs']

        # check if 2020 is taken
        mentee = mentors.get(tw)
        if not mentee:
            # If 2020 has no mentee, they have one now!
            mentors[tw]['id'] = tt
            mentors[tw]['match'] = tw_mentees[tt]
        else:
            # this is kinda me being lazy to allow for the clean_mentors() method
            # to work more easily.
            mentee = mentee['id']

            # If the 2020 is a mentor, gonna need to check compatibility
            if tw_mentees[tt] > tw_mentees[mentee]:
                # New 2022 preferred match
                mentors[tw]['id'] = tt
                mentors[tw]['match'] = tw_mentees[tt]
                if cls_22_copy[mentee]:
                    # ex-mentee has more mentors to try
                    cls_22_free.append(mentee)
            else:
                # New 2022 match rejected
                if tt_mentors:
                    # if there's more mentors, look again
                    cls_22_free.append(tt)

    return mentors


def clean_mentors(mentors):
    # Make sure that the mentors have at least 75% match
    # If not, then free up the mentors
    cleaned_mentors = {}
    menteeless_mentors = []
    for k, v in mentors.items():
        if v['match'] >= 0.75:
            cleaned_mentors[k] = v
        else:
            menteeless_mentors.append(k)
    return cleaned_mentors, menteeless_mentors


def get_mentorless(cls_22, single_mentors):
    matched = {v['id'] for v in single_mentors.values()}

    return {k: v for k, v in cls_22.items() if k not in matched}


def clean_preferences(mentorless):
    for m in mentorless.keys():
        mentorless[m]['prefs'] = SortedDict()
    return mentorless


def create_pairs(cls_20, menteeless_mentors):
    # Don't need a defaultdict here since match percentages
    # not used in clean function
    matches = {}

    cls_20_copy = {k: v for k, v in cls_20.items()}

    # all the logic following is the same as in get_mentors(...)
    # I'll explain any discrepancies with comments
    while menteeless_mentors:
        menteeless = menteeless_mentors.pop(0)
        menteeless_prefs = cls_20_copy[menteeless]['prefs_20']
        tw = max(menteeless_prefs.items(), key=lambda x: x[1])[0]
        tw_val = menteeless_prefs.pop(tw)

        match = matches.get(tw)
        if not match:
            matches[tw] = menteeless
        else:
            #tw_prefs == tw_mentees logically
            tw_prefs = cls_20_copy[tw]['prefs_20']
            if tw_prefs[menteeless] > tw_prefs[match]:
                matches[tw] = menteeless
                if cls_20_copy[match]:
                    menteeless_mentors.append(match)
            else:
                if menteeless_prefs:
                    menteeless_mentors.append(menteeless)

    return matches


def clean_pairs(cls_20, pairs):
    new_pairs = defaultdict(lambda: {})

    # change dictionary into list of pairs (tuples)
    pairings = [(k, v) for k, v in pairs.items()]

    for pair in pairings:
        key = "{}, {}".format(pair[0], pair[1])
        new_pairs[key]["members"] = pair
        new_pairs[key]["prefs"] = SortedDict()
        new_pairs[key]["advice"] = list(set(cls_20[pair[0]]['advice'] + cls_20[pair[1]]['advice']))

    return new_pairs


def get_pair_mentors(cls_20_pairs, mentorless_pairs):
    mentors = {}
    cls_22_free = list(mentorless_pairs.keys())

    cls_20_copy = {k: v for k, v in cls_20_pairs.items()}
    cls_22_copy = {k: v for k, v in mentorless_pairs.items()}

    while cls_22_free:
        tt = cls_22_free.pop(0)
        tt_mentors = cls_22_copy[tt]['prefs']
        tw = max(tt_mentors.items(), key=lambda x: x[1])[0]
        tw_val = tt_mentors.pop(tw)

        mentee = mentors.get(tw)
        if not mentee:
            mentors[tw] = tt
        else:
            tw_mentees = cls_20_copy[tw]['prefs']
            if tw_mentees[tt] > tw_mentees[mentee]:
                mentors[tw] = tt
                if cls_22_copy[mentee]:
                    cls_22_free.append(mentee)
            else:
                if tt_mentors:
                    cls_22_free.append(tt)
    return mentors


def get_pair_name(cls_20, cls_22, single_mentors, pair_mentors):
    matches = {}

    for mentor, mentee in single_mentors.items():
        matches[cls_20[mentor]['name']] = {
            "name": cls_22[mentee['id']]['name'],
            "email": cls_22[mentee['id']]['email'],
        }

    for pair, mentee in pair_mentors.items():
        pair_ids = re.match("(?P<first>\d+), (?P<second>\d+)", pair)

        first_mentor = cls_20[pair_ids.group("first")]['name']
        second_mentor = cls_20[pair_ids.group("second")]['name']

        pair_label = "{}, {}".format(first_mentor, second_mentor)

        matches[pair_label] = {
            "name": cls_22[mentee]['name'],
            "email": cls_22[mentee]['email']
        }

    return matches


def print_matches(final_matches, output_file):
    with open(output_file, 'w') as csvfile:
        headers = ["mentor(s)", "mentee name", "mentee email"]
        writer = csv.DictWriter(csvfile, fieldnames=headers)

        writer.writeheader()
        for mentor, mentee in final_matches.items():
            writer.writerow({
                "mentor(s)": mentor,
                "mentee name": mentee["name"],
                "mentee email": mentee["email"]
            })

# Current solution will allow for person used in more than 1 pair
# in the 2020 class because stable roommate and stable marriage problems
# don't apply and I don't want to think of a new solution at 2:30am
def run(file_location, output_file):
    processed_file = replace_headers(file_location)
    data = get_data(processed_file)

    cls_20, cls_22 = split_years(data)
    cls_20, cls_22 = get_preferences(cls_20, cls_22)

    single_mentors = get_mentors(cls_20, cls_22)
    single_mentors, menteeless_mentors = clean_mentors(single_mentors)

    mentorless = get_mentorless(cls_22, single_mentors)
    mentorless = clean_preferences(mentorless)

    cls_20 = get_pairing_preferences(cls_20)
    cls_20_pairs = create_pairs(cls_20, menteeless_mentors)
    cls_20_pairs = clean_pairs(cls_20, cls_20_pairs)
    cls_20_pairs, mentorless_pairs = get_preferences(cls_20_pairs, mentorless) # can re-use function yaaay
    pair_mentors = get_pair_mentors(cls_20_pairs, mentorless_pairs)
    final_matches = get_pair_name(cls_20, cls_22, single_mentors, pair_mentors)
    print_matches(final_matches, output_file)


if __name__ == "__main__":
    run("data_aug_04_2017.csv", "matches_aug_04_2017.csv")