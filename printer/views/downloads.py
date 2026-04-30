import os
import hashlib
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser

DOWNLOADS_DIR = Path(getattr(settings, 'DOWNLOADS_DIR', os.path.join(settings.BASE_DIR, 'downloads')))
ALLOWED_FILES = {
    'NonborPrintAgent.exe': 'Windows Print Agent',
    'NonborPrinter.apk':    'Android Print Agent',
}


class DownloadListView(APIView):
    """GET /api/v2/downloads/ — yuklab olish mumkin bo'lgan fayllar ro'yxati"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        result = []
        for filename, label in ALLOWED_FILES.items():
            path = DOWNLOADS_DIR / filename
            if path.exists():
                result.append({
                    'filename': filename,
                    'label':    label,
                    'size':     path.stat().st_size,
                    'url':      request.build_absolute_uri(f'/api/v2/downloads/{filename}'),
                })
        return Response({'success': True, 'files': result})


class DownloadFileView(APIView):
    """GET /api/v2/downloads/<filename> — faylni yuklab olish"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, filename):
        if filename not in ALLOWED_FILES:
            raise Http404
        path = DOWNLOADS_DIR / filename
        if not path.exists():
            return Response({'success': False, 'error': 'Fayl hali yuklanmagan'}, status=404)
        mime, _ = mimetypes.guess_type(str(path))
        resp = FileResponse(open(path, 'rb'), content_type=mime or 'application/octet-stream')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp['Content-Length'] = path.stat().st_size
        return resp


class DownloadUploadView(APIView):
    """POST /api/v2/downloads/upload/ — yangi versiya yuklash (admin only)"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        filename  = request.data.get('filename', '')

        if not file_obj or not filename:
            return Response({'success': False, 'error': 'file va filename kerak'}, status=400)

        if filename not in ALLOWED_FILES:
            return Response({
                'success': False,
                'error':   f"Ruxsat berilmagan fayl nomi. Qabul qilinadi: {list(ALLOWED_FILES)}",
            }, status=400)

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest = DOWNLOADS_DIR / filename

        sha256 = hashlib.sha256()
        with open(dest, 'wb') as f:
            for chunk in file_obj.chunks():
                f.write(chunk)
                sha256.update(chunk)

        return Response({
            'success':  True,
            'filename': filename,
            'size':     dest.stat().st_size,
            'sha256':   sha256.hexdigest(),
            'url':      request.build_absolute_uri(f'/api/v2/downloads/{filename}'),
        })
