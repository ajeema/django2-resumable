from django.db.models import FileField
from django.core.files.move import file_move_safe
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from os import path, makedirs
import urllib
from .forms import FormResumableFileField
from .widgets import ResumableWidget

class ResumableFileField(FileField):
    def __init__(self, verbose_name=None, name=None, upload_to='',
                 chunks_upload_to='', **kwargs):
        self.chunks_upload_to = chunks_upload_to
        super().__init__(verbose_name, name, upload_to, **kwargs)  # Updated super call

    def pre_save(self, model_instance, add):

        if not self.upload_to or (not callable(
                self.upload_to) and self.upload_to == self.chunks_upload_to):
            # this condition is verified whether "upload_to" has not been set in the
            # definition of field, or it has been set to the same location of the
            # chunks folder.
            # In those cases, we save some (useless) I/O operations
            # (i.e. deleting, and re-creating the same file twice), and
            # so the default FileField behaviour will be used/returned.
            return super(ResumableFileField, self).pre_save(model_instance, add)

        # if here, upload_to has been set to a different location
        # from the chunks_upload_to
        file = Field.pre_save(self, model_instance, add)
        if file and (not file._committed or self.chunks_upload_to in file.name):
            # Commit the file to storage prior to saving the model
            fpath = urllib.parse.unquote_plus(file.name.replace(settings.MEDIA_URL, self._safe_media_root()))
            basename = path.basename(fpath)
            name = self.generate_filename(model_instance, basename)
            new_fpath = file.storage.get_available_name(
                path.join(self.storage.location, name),
                max_length=self.max_length)
            basefolder = path.dirname(new_fpath)
            if not file.storage.exists(basefolder):
                makedirs(basefolder)
            file_move_safe(fpath, new_fpath)
            # update name
            new_basename = path.basename(new_fpath)
            new_name = self.generate_filename(model_instance, new_basename)
            setattr(model_instance, self.name, new_name)
            file._committed = True
            file.name = new_name
        return file

    def _safe_media_root(self):
        return settings.MEDIA_ROOT.rstrip(path.sep) + path.sep


    def formfield(self, **kwargs):
        content_type_id = ContentType.objects.get_for_model(self.model).id
        defaults = {
            'form_class': FormResumableFileField,
            'widget': ResumableWidget(attrs={
                'content_type_id': content_type_id,
                'field_name': self.name})
        }
        kwargs.update(defaults)
        return super().formfield(**kwargs)
