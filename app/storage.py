from google.cloud import storage

storage_client = storage.Client()

def upload_file_obj(bucket_name, source_file, destination_blob_name):
    """Uploads a file to the bucket."""
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_file(source_file)

def delete_obj(bucket_name, obj_name):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(obj_name)
    blob.delete()
    
def rename_obj(bucket_name, blob_name, new_name):
    """Renames a blob."""
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)
    new_blob = bucket.rename_blob(blob, new_name)
