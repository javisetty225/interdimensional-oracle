from dataclasses import dataclass


@dataclass
class EvalSample:
    question: str
    ground_truth: str


GOLDEN_DATASET: list[EvalSample] = [
    EvalSample(
        question="What is the status of Rick Sanchez?",
        ground_truth="Rick Sanchez is Alive. He is a Human male.",
    ),
    EvalSample(
        question="What species is Morty Smith?",
        ground_truth="Morty Smith is a Human.",
    ),
    EvalSample(
        question="What dimension is Earth C-137 in?",
        ground_truth="Earth C-137 is in Dimension C-137.",
    ),
    EvalSample(
        question="What type of location is the Citadel of Ricks?",
        ground_truth="The Citadel of Ricks is a space station.",
    ),
    EvalSample(
        question="What is the air date of the Pilot episode?",
        ground_truth="The Pilot episode aired on December 2, 2013.",
    ),
    EvalSample(
        question="What species is Birdperson?",
        ground_truth="Birdperson is an Alien of type Bird-Person.",
    ),
    EvalSample(
        question="What is the gender of Summer Smith?",
        ground_truth="Summer Smith is Female.",
    ),
    EvalSample(
        question="What episode code is the first episode of season 3?",
        ground_truth="The first episode of season 3 is S03E01.",
    ),
    EvalSample(
        question="Where does Rick Sanchez currently live?",
        ground_truth="Rick Sanchez is currently at the Citadel of Ricks.",
    ),
    EvalSample(
        question="How many episodes does Birdperson appear in?",
        ground_truth="Birdperson appears in 7 episodes.",
    ),
]