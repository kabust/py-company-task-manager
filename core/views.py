from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views import generic

from core.forms import (
    WorkerNameSearch,
    TaskFiltersSearch,
    TaskForm,
    WorkerCreateForm,
    WorkerUpdateForm,
)
from core.models import Task, Project


@login_required
def index(request: HttpRequest) -> HttpResponse:
    workers_amount = get_user_model().objects.filter(project=request.user.project).count()
    tasks_total_amount = Task.objects.filter(project=request.user.project).count()
    tasks_done = Task.objects.filter(is_completed=True, project=request.user.project).count()

    context = {
        "workers_amount": workers_amount,
        "tasks_total_amount": tasks_total_amount,
        "tasks_done": tasks_done,
    }
    return render(request, "core/index.html", context)


class TaskListView(LoginRequiredMixin, generic.ListView):
    paginate_by = 5

    def get_queryset(self):
        queryset = Task.objects.prefetch_related("assignees")
        project_id = self.request.build_absolute_uri().split("/")[4]
        queryset = queryset.filter(project_id=project_id)
        filters = self.request.GET.getlist("filters")

        if "past_dl" in filters:
            queryset = queryset.filter(deadline__lt=date.today())

        if "urgent" in filters:
            queryset = queryset.filter(priority="Urgent")

        if "done" in filters:
            queryset = queryset.filter(is_completed=True)
        else:
            queryset = queryset.filter(is_completed=False)

        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.request.build_absolute_uri().split("/")[4]

        filters = self.request.GET.getlist("filters")
        context["filters"] = TaskFiltersSearch(initial={"filters": filters})
        context["project"] = Project.objects.get(id=project_id)

        return context


class TaskDetailView(LoginRequiredMixin, generic.DetailView):
    model = Task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context


class TaskCreateView(LoginRequiredMixin, generic.CreateView):
    model = Task
    form_class = TaskForm

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        return reverse("core:task-list", args=(self.request.user.project.id,))


class TaskUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = Task
    form_class = TaskForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs["request"] = self.request
        return kwargs

    def get(self, request, *args, **kwargs):
        obj = super().get_object()

        if obj.project != self.request.user.project:
            return HttpResponse("Unauthorized", status=405)

        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("core:task-list", args=(self.get_object().project.id,))

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context


class TaskDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = Task

    def get(self, request, *args, **kwargs):
        obj = super().get_object()

        if obj.project != self.request.user.project:
            return HttpResponse("Unauthorized", status=405)

        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("core:task-list", args=(self.get_object().project.id,))

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context


def toggle_completed(request: HttpRequest, pk) -> HttpResponseRedirect | HttpResponse:
    task = Task.objects.get(pk=pk)

    if request.user in task.assignees.all():
        task.is_completed = not task.is_completed
        task.save()
    else:
        return HttpResponse("Unauthorized", status=405)

    return HttpResponseRedirect(reverse("core:task-detail", args=(pk,)))


class WorkerListView(LoginRequiredMixin, generic.ListView):
    paginate_by = 10

    def get_queryset(self):
        name = self.request.GET.get("name")
        queryset = get_user_model().objects.all()

        if name:
            return queryset.filter(
                Q(first_name__icontains=name) | Q(last_name__icontains=name)
            )
        return queryset

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        name = self.request.GET.get("name", "")
        context["search_form"] = WorkerNameSearch(initial={"name": name})

        context["num_workers"] = get_user_model().objects.count()

        return context


class WorkerDetailView(LoginRequiredMixin, generic.DetailView):
    model = get_user_model()
    queryset = get_user_model().objects.prefetch_related("tasks")


class WorkerCreateView(generic.CreateView):
    model = get_user_model()
    form_class = WorkerCreateForm
    success_url = reverse_lazy("core:index")

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context


class WorkerUpdateView(generic.UpdateView):
    form_class = WorkerUpdateForm

    def get_queryset(self):
        user = get_user_model().objects.filter(pk=self.request.user.pk)
        return user

    def get_success_url(self):
        pk = self.request.user.pk
        return reverse("core:worker-detail", args=(pk,))

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        context["previous_url"] = self.request.META.get("HTTP_REFERER")
        return context


class ProjectListView(LoginRequiredMixin, generic.ListView):
    model = Project

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        context["users_project"] = self.request.user.project.pk
        return context
