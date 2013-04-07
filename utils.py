import uuid

def create_unique_label(label):
    """
    Create a unique label.
    For now we should create a unique label based on UUID
    """
    return uuid.uuid1().hex
