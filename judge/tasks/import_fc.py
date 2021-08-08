import os
import shutil
import logging

from celery import shared_task
from django.conf import settings
from django.utils.translation import gettext as _

from judge.utils import import_fc_helper as helper
from judge.utils.celery import Progress

__all__ = ('import_free_contest', )

logger = logging.getLogger('import_fc')


@shared_task(bind=True)
def import_free_contest(self, contest_name, contest_id, test_link, csv_link, contest_date):

    # We want to read the log for each submit
    # instead of the whole log file
    # so we erase all the old data before do the new one
    helper.clear_logger()

    if helper.contest_imported(contest_id):
        logger.info("Contest %s already existed", contest_id)
        return

    # download test_folder
    # After this, all folder tree looks like this:
    # folder_path/
    #   problem_id1.zip
    #   problem_id2.zip
    #   ...
    with Progress(self, 3, stage=_('Downloading test folder, this could take several minutes')) as p:
        folder_path = helper.download_test(test_link, contest_id)
        p.done += 1

        # Because the gdrive process can make many sub-directories
        # so we do some format here.
        dummy_folder = [x for x in os.listdir(folder_path) if not os.path.isfile(os.path.join(folder_path, x))][0]
        helper.format_folder_structure(folder_path, contest_id)
        shutil.rmtree(os.path.join(folder_path, dummy_folder))
        p.done += 1

        # move checker to correct folder
        problem_ids = set(test.lower()[:-4] for test in os.listdir(folder_path))
        helper.move_checker(folder_path, problem_ids)
        p.done += 1

    # create init.yml for problems
    with Progress(self, len(problem_ids), stage=_('Generate init.yml files')) as p:
        for test in problem_ids:
            if test == 'input':
                p.done += 1
                continue

            checker_path = os.path.join(folder_path, test + ".cpp")
            if not os.path.exists(checker_path):
                checker_path = None
            problem_code = test.split('.')[0].strip()
            for i in range(1, 10):
                problem_code = problem_code.replace(f'({i})', '').strip()

            logger.info("Create test data for: %s", problem_code)
            helper.create_test_data(
                contest_id, problem_code,
                os.path.join(folder_path, test + ".zip"),
                settings.DMOJ_PROBLEM_DATA_ROOT,
                checker_path,
            )
            p.done += 1

    # import problems to site
    with Progress(self, len(problem_ids), stage=_('Import problem to site')) as p:
        for test in problem_ids:
            if test == 'input':
                p.done += 1
                continue

            problem_code = test.split('.')[0].strip()
            for i in range(1, 10):
                problem_code = problem_code.replace(f'({i})', '').strip()

            pdf_link = helper.BASE_URL + "/" + contest_id.upper() + "/" + problem_code + ".pdf"
            logger.info("Import %s to site", problem_code)
            helper.create_new_problem(
                contest_id.lower() + "_" + problem_code.lower(),
                contest_name + " - " + problem_code.upper(),
                pdf_link,
            )
            p.done += 1

    logger.info("Create contest % s", contest_name)
    helper.new_contest(contest_id.lower(), contest_name, contest_date)
