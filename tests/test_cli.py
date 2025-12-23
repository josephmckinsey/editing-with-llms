import os
import tempfile
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from editing_with_llms import cli
import re


@pytest.fixture
def sample_text():
    return "This is a smaple text with a typo."


@pytest.fixture
def expected_llm_output():
    return "Found typo: smaple (should be sample)\nExplanation: Typo in word."


@patch("editing_with_llms.cli.llm")
def test_typo_checker_basic(mock_llm, sample_text, expected_llm_output):
    # Mock llm.get_model().prompt() and streaming
    mock_response = MagicMock()
    mock_response.__iter__.return_value = [expected_llm_output]
    mock_response.text.return_value = expected_llm_output
    mock_llm.get_model.return_value.prompt.return_value = mock_response

    runner = CliRunner()
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name
    try:
        result = runner.invoke(cli.main, [tmp_path])
        assert result.exit_code == 0
        assert expected_llm_output in result.output
        # Check output file
        with open("output.txt", "r", encoding="utf-8") as f:
            file_output = f.read()
        assert expected_llm_output in file_output
    finally:
        os.remove(tmp_path)
        if os.path.exists("output.txt"):
            os.remove("output.txt")


@pytest.mark.skip(reason="This does a terrible with llama3.2:latest")
def test_typo_checker_real_llm(sample_text):
    """
    This test runs the typo checker with the real llm package (no mocking),
    then uses the LLM itself to evaluate if the output is a reasonable typo report.
    Skips if no API key is set or llm is not configured.
    """
    import llm

    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    # Run the CLI using CliRunner
    runner = CliRunner()
    result = runner.invoke(cli.main, [str(tmp_path)])
    assert result.exit_code == 0
    output = result.output
    print(output)
    # Now use llm to evaluate the output
    eval_prompt = f"Evaluate the following typo report for the text: '{sample_text}'. Does this report typos with []? Answer 'yes' or 'no' and explain."
    report = f"Original prompt:\n\n{sample_text}\n\nReport:\n{output}"
    model = llm.get_model()
    eval_response = model.prompt(report, system=eval_prompt)
    eval_text = eval_response.text()
    print("\n--- LLM Evaluation ---\n")
    print(eval_text)
    assert "yes" in eval_text.lower() or "no in eval_text.lower", (
        "Did not find conclusive response"
    )
    assert "yes" in eval_text.lower()


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,expected_typos",
    [
        ("This is a smaple text with a typo.", ["smaple"]),
        ("He recieved teh package adress yesterday.", ["recieved", "teh", "adress"]),
        (
            "Its important to seperate the data and ensure thier correct.",
            ["Its", "seperate", "thier"],
        ),
        (
            "The accomodation was definately not upto our expections.",
            ["accomodation", "definately", "upto", "expections"],
        ),
        (
            "She occured to have alot of knoledge about the subject.",
            ["occured", "alot", "knoledge"],
        ),  # grammatical errors
        ("She go to the store yesterday.", ["go"]),  # should be 'went'
        ("He don't like apples.", ["don't"]),  # should be 'doesn't'
        ("There is many reasons to try.", ["is"]),  # should be 'are'
        ("The informations are useful.", ["informations"]),  # should be 'information'
        ("He was more taller than his brother.", ["more"]),  # should be 'taller'
    ],
)
def test_typo_checker_various_typos(sample_text, expected_typos):
    """
    Parameterized test: runs the typo checker with various tricky typos and checks if the output contains the expected typo words in brackets.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(cli.main, [str(tmp_path)])
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")

    found_words = re.findall(r"\[([^\[\]]+)\]", output)
    for typo in expected_typos:
        typo_in_found = False
        for found in found_words:
            if typo in found:
                typo_in_found = True
                break
        assert typo_in_found, (
            f"Expected typo '{typo}' not found in output: {found_words}"
        )

    # Clean up
    os.remove(tmp_path)
    if os.path.exists("output.txt"):
        os.remove("output.txt")


@patch("editing_with_llms.cli.llm")
def test_clarity_checker_basic(mock_llm):
    sample_text = "The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps."
    expected_llm_output = "- [The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps.]"
    mock_response = MagicMock()
    mock_response.__iter__.return_value = [expected_llm_output]
    mock_response.text.return_value = expected_llm_output
    mock_llm.get_model.return_value.prompt.return_value = mock_response

    runner = CliRunner()
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name
    try:
        result = runner.invoke(cli.main, ["--check", "clarity", tmp_path])
        assert result.exit_code == 0
        assert expected_llm_output in result.output
    finally:
        os.remove(tmp_path)
        if os.path.exists("output.txt"):
            os.remove("output.txt")


@patch("editing_with_llms.cli.llm")
def test_reader_checker_basic(mock_llm):
    sample_text = "How can we handle both state and error handling in a Haskell program? The solution uses a monad transformer stack to manage side effects in a lazy functional language."
    expected_llm_output = "- [The solution uses a monad transformer stack to manage side effects in a lazy functional language.] (This sentence uses advanced functional programming terminology that may not be familiar to a mathematician with only some programming experience.)"
    mock_response = MagicMock()
    mock_response.__iter__.return_value = [expected_llm_output]
    mock_response.text.return_value = expected_llm_output
    mock_llm.get_model.return_value.prompt.return_value = mock_response

    runner = CliRunner()
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name
    try:
        result = runner.invoke(
            cli.main,
            [
                "--check",
                "reader",
                "--reader",
                "a mathematician who knows some programming",
                tmp_path,
            ],
        )
        assert result.exit_code == 0
        assert expected_llm_output in result.output
    finally:
        os.remove(tmp_path)
        if os.path.exists("output.txt"):
            os.remove("output.txt")


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,expected_clarity_flags",
    [
        (
            "Our team met to discuss the project timeline. The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps. Everyone agreed to meet again next week.",
            [
                "The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps."
            ],
        ),
        ("He went to the store. She bought apples.", []),  # all clear sentences
        (
            "We sought to use experiments and statistical analysis to shed light on the issue. The data, which was collected over several years, and despite the challenges, was analyzed. The results were promising.",
            [
                "The data, which was collected over several years, and despite the challenges, was analyzed."
            ],
        ),
    ],
)
def test_clarity_checker_various(sample_text, expected_clarity_flags):
    """
    Parameterized test: runs the clarity checker and checks if the output contains the expected unclear/confusing sentences in brackets.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(cli.main, ["--check", "clarity", tmp_path])
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")

    found_flags = re.findall(r"\[([^\[\]]+)\]", output)
    for flag in expected_clarity_flags:
        assert any(flag in found for found in found_flags), (
            f"Expected unclear/confusing sentence '{flag}' not found in output: {found_flags}"
        )
    # Clean up
    os.remove(tmp_path)
    if os.path.exists("output.txt"):
        os.remove("output.txt")


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,reader,expected_reader_flags",
    [
        (
            "How can we handle both state and error handling in a Haskell program? The solution uses a monad transformer stack to manage side effects in a lazy functional language. The program first reads input from a file.",
            "a mathematician who knows some programming",
            [
                "The solution uses a monad transformer stack to manage side effects in a lazy functional language."
            ],
        ),
        (
            "The cat sat on the mat. The dog barked.",
            "a child",
            [],
        ),  # no accessibility issues
        (
            "The eigenvalues of the Hermitian operator are real. The experiment was conducted in a laboratory. The results were recorded.",
            "a high school student",
            ["The eigenvalues of the Hermitian operator are real."],
        ),
    ],
)
def test_reader_checker_various(sample_text, reader, expected_reader_flags):
    """
    Parameterized test: runs the reader checker and checks if the output contains the expected accessibility issues in brackets.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["--check", "reader", "--reader", reader, tmp_path],
    )
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")

    found_flags = re.findall(r"\[([^\[\]]+)\]", output)
    for flag in expected_reader_flags:
        assert any(flag in found for found in found_flags), (
            f"Expected accessibility issue '{flag}' not found in output: {found_flags}"
        )
    # Clean up
    os.remove(tmp_path)
    if os.path.exists("output.txt"):
        os.remove("output.txt")


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,reader,function_desc,expected_flags",
    [
        # Convince, business manager
        (
            "Our new analytics platform increased revenue by 15% for three major clients last quarter. I enjoyed working on the user interface because it was a fun design challenge. It requires no additional IT staff and integrates with existing tools.",
            "a business manager",
            "convince",
            [
                "I enjoyed working on the user interface because it was a fun design challenge."
            ],
        ),
        # Convince, developer
        (
            "Switching to our framework reduced build times by 40%. I have always wanted to work on a project like this. The framework is open source and has an active community.",
            "a developer",
            "convince",
            ["I have always wanted to work on a project like this."],
        ),
        # Inform, beginner Python programmer
        (
            "A Python list is an ordered collection of items. I first learned about lists when I was in college, and I found them fascinating. You can add items to a list using the append() method.",
            "a beginner Python programmer",
            "inform",
            [
                "I first learned about lists when I was in college, and I found them fascinating."
            ],
        ),
        # Inform, business manager
        (
            "Our new dashboard provides real-time sales data. I decided to write about this feature because I think dashboards are cool. The dashboard can be accessed from any device.",
            "a business manager",
            "inform",
            [
                "I decided to write about this feature because I think dashboards are cool."
            ],
        ),
        # Good example: should not flag anything
        (
            "A Python list is an ordered collection of items. You can add items to a list using the append() method. Lists are mutable, which means you can change their contents after creation.",
            "a beginner Python programmer",
            "inform",
            [],
        ),
        (
            "Our new analytics platform increased revenue by 15% for three major clients last quarter. It requires no additional IT staff and integrates with existing tools. Customer support is available 24/7.",
            "a business manager",
            "convince",
            [],
        ),
    ],
)
def test_function_checker_various(sample_text, reader, function_desc, expected_flags):
    """
    Parameterized test: runs the function checker and checks if the output contains the expected flagged sentences in brackets.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "--check",
            "function",
            "--reader",
            reader,
            "--function",
            function_desc,
            tmp_path,
        ],
    )
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")

    found_flags = re.findall(r"\[([^\[\]]+)\]", output)
    for flag in expected_flags:
        assert any(flag in found for found in found_flags), (
            f"Expected function issue '{flag}' not found in output: {found_flags}"
        )
    # Clean up
    os.remove(tmp_path)
    if os.path.exists("output.txt"):
        os.remove("output.txt")


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,expected_function_guess",
    [
        # Article that clearly aims to inform
        (
            "Python is a versatile programming language used in web development, data science, and automation. This article will explain why Python is a great choice for beginners and professionals alike.",
            "inform",
        ),
        # Article that tries to convince
        (
            "Investing in renewable energy is not just good for the planet, it's good for your portfolio. Long-term returns require long-term thinking, and the zero marginal cost nature of renewable energy energizes your capital.",
            "convince",
        ),
        # Article that entertains
        (
            "Have you ever wondered what your cat is really thinking? Join us for a humorous journey into the feline mind. New science has given us a new window into our little critters.",
            "entertain",
        ),
        # Article that challenges
        (
            "Most people believe multitasking makes them more productive. However, the science of focus tells us that distractions can matter more than leaders, employees, and moms expect.",
            "challenge",
        ),
    ],
)
def test_guess_function_of_article(sample_text, expected_function_guess):
    """
    Test that the LLM can guess the function of an article/introduction.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "--check",
            "guess-function",
            "--reader",
            "a general reader",
            tmp_path,
        ],
    )
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")
    assert expected_function_guess in output.lower()
    os.remove(tmp_path)


@pytest.mark.skip(reason="It's expensive to run this test too often")
@pytest.mark.parametrize(
    "sample_text,expected_value_guess",
    [
        # Article that clearly values practicality
        (
            "Python is a practical language for solving real-world problems. Its syntax is simple and readable, making it accessible to many.",
            "practicality",
        ),
        # Article that values innovation
        (
            "Breakthroughs in renewable energy technology are reshaping our world. Embracing innovation is key to a sustainable future.",
            "innovation",
        ),
        # Article that values humor
        (
            "Why did the computer go to therapy? It had too many bytes of emotional baggage! Let's explore the lighter side of tech.",
            "humor",
        ),
        # Article that values tradition
        (
            "For centuries, artisans have passed down their skills through generations. Honoring tradition keeps our heritage alive.",
            "tradition",
        ),
    ],
)
def test_guess_value_of_article(sample_text, expected_value_guess):
    """
    Test that the LLM can guess the value or theme of an article/introduction.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "--check",
            "guess-value",
            "--reader",
            "a general reader",
            tmp_path,
        ],
    )
    assert result.exit_code == 0
    output = result.output
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{output}")
    assert expected_value_guess in output.lower()
    os.remove(tmp_path)


@pytest.mark.parametrize(
    "sample_text,expected_audiences",
    [
        # General public / Beginners
        (
            "Python is a versatile programming language used in web development, data science, and automation. This article will explain why Python is a great choice for beginners and professionals alike.",
            ["beginners", "beginner", "novice", "newcomer", "general public", "learner", "student"],
        ),
        # Business/finance/investors
        (
            "Investing in renewable energy is not just good for the planet, it's good for your portfolio. Long-term returns require long-term thinking, and the zero marginal cost nature of renewable energy energizes your capital.",
            ["business", "investor", "professional", "financial", "entrepreneur", "executive", "manager", "finance"],
        ),
        # Children/general public/cat owners
        (
            "Have you ever wondered what your cat is really thinking? Join us for a humorous journey into the feline mind. New science has given us a new window into our little critters.",
            ["children", "child", "general", "public", "cat owner", "pet owner", "enthusiast", "casual reader"],
        ),
        # Students/academics
        (
            "The eigenvalues of the Hermitian operator are real. The experiment was conducted in a laboratory. The results were recorded.",
            ["students", "student", "academic", "researcher", "scientist", "physics", "undergraduate", "graduate"],
        ),
    ],
)
def test_guess_reader_of_article(sample_text, expected_audiences):
    """
    Test that the LLM can guess the intended audience or reader profile of an article/introduction.
    Accepts any of the synonyms in expected_audiences list.
    """
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(sample_text)
        tmp_path = tmp.name

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "--check",
            "guess-reader",
            tmp_path,
        ],
    )
    assert result.exit_code == 0
    output = result.output.lower()
    print(f"\n[Prompted text]: {sample_text}\n[LLM Output]:\n{result.output}")

    # Check if ANY of the expected audience terms appear in the output
    found_match = any(audience.lower() in output for audience in expected_audiences)
    assert found_match, f"None of {expected_audiences} found in output"

    os.remove(tmp_path)
