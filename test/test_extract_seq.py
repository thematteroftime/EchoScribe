from src.job import extract_seq_from_filename

def test_simple():
    assert extract_seq_from_filename("chunk_001.wav") == 1
    assert extract_seq_from_filename("rec_2025_045.wav") == 45
    assert extract_seq_from_filename("001.wav") == 1
    assert extract_seq_from_filename("no_digits.wav") == -1
