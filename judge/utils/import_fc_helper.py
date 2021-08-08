import datetime
import logging
import os
import re
import shutil
import subprocess
import tempfile
from zipfile import ZipFile

import patoolib
from django.conf import settings


def set_up_logger(logger):
    logger.setLevel(logging.INFO)
    f_handler = logging.FileHandler(settings.VNOJ_IMPORT_FC_LOG_PATH, mode='w')
    f_handler.setLevel(logging.INFO)
    f_handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(name)s %(message)s"))
    logger.addHandler(f_handler)


def clear_logger():
    with open(settings.VNOJ_IMPORT_FC_LOG_PATH, mode='w'):
        pass


logger = logging.getLogger('import_fc')
set_up_logger(logger)

PATTERN = r"drive\.google\.com/(file/d|drive/folders|drive/u/0/folders)/([\w\-_]+)[\?/]?"

CHECKER_PATH = None
TEMP_PATH = None


def remove_tempfolder(path):
    if path and os.path.exists(path):
        shutil.rmtree(path)


def init_tempfolder():
    global CHECKER_PATH, TEMP_PATH
    remove_tempfolder(CHECKER_PATH)
    remove_tempfolder(TEMP_PATH)
    TEMP_PATH = tempfile.mkdtemp()
    CHECKER_PATH = tempfile.mkdtemp()


BASE_URL = "http://vnoi-admin.github.io/statements/FC"

INPUT_EXTS = ["in", "inp", "dat"]
INPUT_NAMES = ["in", "input"]
OUTPUT_EXTS = ["ok", "out", "ans", "ou", "a", "sol", "diff"]
OUTPUT_NAMES = ["ans", "output", "expect", "ouput"]
SKIP_EXTS = ["txt~", "txt", "cpp", "py", "png", "jpg", "pdf", "zip", "sh", "sh~", "desc", "cfg", "pas", "yaml", "ini"]


def get_googledrive_id(folder_link: str):
    global PATTERN
    return re.findall(PATTERN, folder_link)[0][1]


def safe_rename(src, dst):
    if (src == dst):
        return
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(src, dst)


def create_new_problem(code, name, link):
    from django.utils.timezone import make_aware
    from judge.models import Language, Problem, ProblemGroup, ProblemType

    if Problem.objects.filter(code=code).count() > 0:
        x = Problem.objects.get(code=code)
        x.name = name
        x.save()
        logger.info("Skipped %s", code)
        return
    points = 0.5
    if "fcb" in code:
        points = 0.1
    x = Problem(
        code=code,
        name=name,
        pdf_url=link,
        group=ProblemGroup.objects.get(name="FC"),
        time_limit=1,
        memory_limit=256 * 1024,
        points=points,
        partial=True,
        date=make_aware(datetime.datetime.now()),
        is_manually_managed=True,
        is_public=True,
        description="**Lưu ý**: các bạn không nhập, xuất dữ liệu bằng file kể cả khi đề bài có yêu cầu. Đọc,"
        " ghi dữ liệu được thực hiện ở stdin và stdout.",
    )
    x.save()
    x.allowed_languages.set(Language.objects.all())
    x.types.set([ProblemType.objects.get(name="uncategorized")])
    x.save()
    return x


def new_contest(code, name, date):
    from django.utils.timezone import make_aware
    from judge.models import Contest, ContestProblem, Problem, Profile
    day, month, year = date
    if Contest.objects.filter(key=code).count() > 0:
        x = Contest.objects.get(key=code)
    else:
        x = Contest(
            key=code,
            name=name,
            start_time=make_aware(datetime.datetime(year, month, day, hour=19 - 7)),
            end_time=make_aware(datetime.datetime(year, month, day, hour=22 - 7)),
            is_visible=True,
            use_clarifications=False,
            og_image='/martor/freecontest.png',
            logo_override_image='/martor/freecontest.png',
            description=f"{name}",
            summary=f"{name}",
        )
        x.save()
    x.key = code
    x.name = name
    x.description = f"{name}"
    x.summary = f"{name}"

    x.authors.set([Profile.objects.get(user__username='admin')])
    x.save()
    problems = Problem.objects.filter(code__startswith=code)
    for stt, p in enumerate(problems):
        try:
            ContestProblem(
                problem=p,
                contest=x,
                points=50,
                order=stt + 1,
            ).save()
        except Exception as e:
            logger.info(repr(e))
            continue


def fix_input_output(inputs, outputs):
    input_ext = inputs[0][inputs[0].find('.'):]
    output_ext = outputs[0][outputs[0].find('.'):]
    input_names = set(name[:name.find('.')] for name in inputs)
    output_names = set(name[:name.find('.')] for name in outputs)
    names = input_names.intersection(output_names)
    inputs = [name + input_ext for name in names]
    outputs = [name + output_ext for name in names]
    return inputs, outputs


def create_test_data(contest_id, problem_code, zip_path, dst_folder, checker_path=None):
    zip_name = problem_code + ".zip"
    data = "archive: " + zip_name + "\n"
    if checker_path is not None:
        data += "checker:\n"
        data += "  args:\n"
        data += "    files: checker.cpp\n"
        data += "    lang: CPP17\n"
        data += "    type: cms\n"
        data += "  name: bridged\n"
    else:
        data += "checker: standard\n"

    data += "test_cases:\n"
    with ZipFile(zip_path, "r") as zip_file:
        test_cases = zip_file.namelist()
        inputs = []
        outputs = []
        for case in test_cases:
            if case.count('__MACOSX') > 0:
                continue
            if case.count('.') == 0 and re.search(r'^\d+$', case) is None:
                continue
            ext = case.split(".")[-1].lower()
            name = case.split('/')[-1].split(".")[0].lower()
            if ext in SKIP_EXTS:
                continue
            if ext in INPUT_EXTS or name.lower() in INPUT_NAMES or re.search(r'(in|inp)\.\d+', case.lower()) \
               or re.search(r'^\d+$', case):
                inputs.append(case)
            elif ext in OUTPUT_EXTS or name.lower() in OUTPUT_NAMES or re.search(r'(out|ans)\.\d+', case.lower()):
                outputs.append(case)
            elif len(case.split('.')) == 3:
                middle = case.split('.')[1].lower()
                if middle in INPUT_NAMES:
                    inputs.append(case)
                elif middle in OUTPUT_NAMES:
                    outputs.append(case)
                else:
                    raise Exception("Cannot found ext for `" + str(case) + "`")
            else:
                raise Exception("Cannot found ext for `" + str(case) + "`")
        if contest_id == 'fc043' and problem_code == 'kinver':
            inputs, outputs = fix_input_output(inputs, outputs)
        if len(inputs) != len(outputs):
            # execption because this problem doesn't need output file
            if contest_id.lower() == 'fc084' and problem_code.lower() == 'math':
                while len(outputs) < len(inputs):
                    outputs.append(outputs[-1])
            else:
                raise Exception("Inputs and outputs has different number of files")

        inputs.sort()
        outputs.sort()
        for inp, out in zip(inputs, outputs):
            data += "- in: \"" + inp + "\"\n"
            data += "  out: \"" + out + "\"\n"
            data += "  points: 1\n"
    # write init file
    problem_path = os.path.join(dst_folder, contest_id + "_" + problem_code)
    if not os.path.exists(problem_path):
        os.mkdir(problem_path)
    open(os.path.join(problem_path, "init.yml"), "w").write(data)
    # cp zip path
    safe_rename(zip_path, os.path.join(problem_path, zip_name))
    if checker_path:
        safe_rename(checker_path, os.path.join(problem_path + "checker.cpp"))


def convert_to_zip(rar_file_path, file_name, dst_folder):
    logger.info("Found a rar file (%s) instead of zip, converting to zip", rar_file_path)
    temp_path = tempfile.mkdtemp()
    patoolib.extract_archive(rar_file_path, outdir=temp_path)
    shutil.make_archive(os.path.join(dst_folder, + file_name[:-4]), 'zip', temp_path)
    os.remove(rar_file_path)
    shutil.rmtree(temp_path)
    return file_name[:-4] + '.zip'


def format_zip_file_name(file_name):
    file_name = file_name.lower()
    if file_name.count('-'):
        raise Exception(f"unexpected dash `-` in file {file_name}")

    pattern = r'(\w) \(\d\).zip'
    return re.sub(pattern, lambda x: x.group(1) + '.zip', file_name)


def format_folder_structure(folder_path, contest_id):
    for path, subdirs, files in os.walk(folder_path):
        for name in files:
            file_path = os.path.join(path, name)
            file_name = file_path[file_path.rfind("/") + 1:]
            file_name = file_name.lower()
            file_ext = file_name.split('.')[-1]
            if file_ext == "cpp":
                logger.info("Found checker: %s", file_name)
                safe_rename(file_path, os.path.join(CHECKER_PATH, contest_id + "_" + file_name))
            else:
                if file_name.count('.') == 0:
                    continue
                SKIP_TEST_EXTS = ['pdf', 'doc', 'docx', 'exe', 'pas', 'java']
                if file_ext in SKIP_TEST_EXTS:
                    continue
                if file_ext == 'rar':
                    file_name = convert_to_zip(file_path, file_name, path)
                    file_path = os.path.join(path, file_name)
                if file_ext != "zip":
                    raise Exception("Wrong file type " + str(file_name))

                safe_rename(file_path, os.path.join(folder_path, format_zip_file_name(file_name)))


def move_checker(folder_path, problem_ids):
    checkers = os.listdir(CHECKER_PATH)
    for checker in checkers:
        checker = checker.lower()
        name = None
        for p_id in problem_ids:
            if p_id in checker:
                name = p_id
                break

        if name is None:
            continue
        safe_rename(os.path.join(CHECKER_PATH, checker), os.path.join(folder_path, name + ".cpp"))


def contest_imported(contest_id):
    from judge.models import Contest
    return Contest.objects.filter(key=contest_id).count() > 0


def logging_call(popenargs, **kwargs):
    process = subprocess.Popen(popenargs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def check_io():
        while True:
            output = process.stdout.readline().decode()
            if output:
                logger.info(output)
            else:
                break

    # keep checking stdout/stderr until the child exits
    while process.poll() is None:
        check_io()


def download_test(folder_link, contest_id):
    logger.info("Downloading test...")
    init_tempfolder()
    folder_id = get_googledrive_id(folder_link)
    folder_path = os.path.join(TEMP_PATH, contest_id)
    logging_call([
        "gdrive",
        "download",
        "--recursive",
        "--skip",
        folder_id,
        "--path",
        folder_path,
    ],
    )
    return folder_path
