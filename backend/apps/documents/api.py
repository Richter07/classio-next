from django.http import Http404, HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.permissions import IsStaff, SessionAuth

from . import jobs


class JobView(APIView):
    authentication_classes = [SessionAuth]
    permission_classes = [IsStaff]

    def get(self, request, job_id):
        state = jobs.state_for(job_id, request.user.pk, request.school.pk)
        if state is None:
            raise Http404
        return Response({"status": state["status"], "filename": state["filename"],
                         "error": state.get("error")})


class JobFileView(JobView):
    def get(self, request, job_id):
        state = jobs.state_for(job_id, request.user.pk, request.school.pk)
        pdf = jobs.pdf_for(job_id) if state and state["status"] == "done" else None
        if pdf is None:
            raise Http404
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{state["filename"]}"'
        response["Cache-Control"] = "private, no-store"
        return response
