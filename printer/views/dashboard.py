from django.shortcuts import render

def agent_dashboard(request):
    return render(request, "agent_dashboard.html")
