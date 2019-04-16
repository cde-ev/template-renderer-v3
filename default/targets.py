
import re
import csv
import os

from globals import target_function


@target_function
def tnletters(event, config, output_dir, match):
    # FIXME rework for new data model
    # Filter participants
    if match is not None:
        regex = re.compile(match)
        participants = [p for p in event.participants if regex.search("{} {}".format(p.first_name, p.last_name))]
    else:
        participants = event.participants

    # Create output subdir
    output_dir = os.path.join(output_dir, 'tnletters')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Create MailMerge CSV file
    with open(os.path.join(output_dir, 'tnletter_mailmerge.csv'), 'w') as csvfile:
        spamwriter = csv.writer(csvfile)
        spamwriter.writerow(["Vorname", "Nachname", "Email", "Datei"])
        for p in participants:
            spamwriter.writerow([p.first_name,
                                 p.last_name,
                                 p.email,
                                 os.path.join(os.path.realpath(output_dir), "tnletter_{}.pdf".format(p.id))])

    return [('tnletter.tex', {'participant': p}, 'tnletter_{}'.format(p.id), False, output_dir)
            for p in participants]

