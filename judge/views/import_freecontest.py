from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
# from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import FormView

from judge.tasks import import_free_contest
from judge.utils.celery import redirect_to_task_status
from judge.utils.views import TitleMixin, generic_message


class ImportFreeContestForm(forms.Form):
    contest_name = forms.CharField(label="Contest name", max_length=100)
    contest_id = forms.CharField(label="Contest id", max_length=100)
    test_folder_link = forms.URLField(label=_('Google drive link to test folder'), max_length=100)
    csv_rank_link = forms.URLField(label=_('Google drive link to csv ranking'), max_length=100)
    contest_date = forms.DateField(label=_('contest date'), widget=forms.DateInput(attrs={'type': 'date'}))

    # contest_name, contest_id, test_link, csv_link, contest_date


class ImportFreeContest(LoginRequiredMixin, TitleMixin, FormView):
    template_name = 'freecontest/new.html'
    form_class = ImportFreeContestForm
    success_url = '/'

    title = _('Import new contest')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super(ImportFreeContest, self).dispatch(request, *args, **kwargs)
        return generic_message(request, _("Can't access"),
                               _('You are not allowed to view this link.'), status=403)

    def form_valid(self, form):
        contest_name = form.cleaned_data.get("contest_name")
        contest_id = form.cleaned_data.get("contest_id")
        test_link = form.cleaned_data.get("test_folder_link")
        csv_link = form.cleaned_data.get("csv_rank_link")
        contest_date = form.cleaned_data.get("contest_date")
        # print(dir(contest_date))
        contest_date = (contest_date.day, contest_date.month, contest_date.year)
        # print(contest_date)
        status = import_free_contest.delay(contest_name, contest_id, test_link, csv_link, contest_date)
        return redirect_to_task_status(
            status, message=_('Importing Free contest %s') % (contest_name,),
            redirect='/import_fc/new/',
        )
