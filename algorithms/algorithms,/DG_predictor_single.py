#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(eq=False)
class Item:
    val: int = -1

    def clone(self) -> "Item":
        return Item(self.val)

    def __str__(self) -> str:
        return str(self.val)

    def __hash__(self) -> int:
        return hash(self.val)

    def equals(self, other) -> bool:
        return isinstance(other, Item) and self.val == other.val

    def __eq__(self, other) -> bool:
        return isinstance(other, Item) and self.val == other.val

    def __lt__(self, other: "Item") -> bool:
        return self.val < other.val


class Sequence:
    def __init__(self, sequence_id: int, items: Optional[List[Item]] = None):
        self.id = sequence_id
        self.items: List[Item] = list(items) if items is not None else []

    @staticmethod
    def fromString(sequenceId: int, input_str: str) -> "Sequence":
        sequence = Sequence(sequenceId)
        if input_str:
            for token in input_str.split():
                sequence.addItem(Item(int(token)))
        return sequence

    def clone(self) -> "Sequence":
        copy = Sequence(self.id)
        for item in self.items:
            copy.items.append(item.clone())
        return copy

    def getId(self) -> int:
        return self.id

    def getItems(self) -> List[Item]:
        return self.items

    def get(self, index: int) -> Item:
        return self.items[index]

    def size(self) -> int:
        return len(self.items)

    def addItem(self, item: Item) -> None:
        self.items.append(item)

    def getLastItems(self, length: int, offset: int) -> Optional["Sequence"]:
        truncatedSequence = Sequence(0)
        size = self.size() - offset
        if not self.items:
            return None
        elif length > size:
            truncatedSequence.items = list(self.items[0:size])
        else:
            truncatedSequence.items = list(self.items[(size - length):size])
        return truncatedSequence

    def print(self) -> None:
        print(str(self), end="")

    def __str__(self) -> str:
        return "".join(f"({it}) " for it in self.items) + "    "

    def setID(self, newid: int) -> None:
        self.id = newid

    def equals(self, other: "Sequence") -> bool:
        return self.id == other.id and len(self.items) == len(other.items) and all(a == b for a, b in zip(self.items, other.items))

    def __eq__(self, other) -> bool:
        return isinstance(other, Sequence) and self.equals(other)

    def __hash__(self) -> int:
        return hash((self.id, tuple(self.items)))


class Profile:
    parameters: Dict[str, str] = {}

    def __init__(self) -> None:
        Profile.parameters = {}

    @staticmethod
    def paramDouble(name: str):
        value = Profile.parameters.get(name)
        return None if value is None else float(value)

    @staticmethod
    def paramInt(name: str):
        value = Profile.parameters.get(name)
        return None if value is None else int(value)

    @staticmethod
    def paramFloat(name: str):
        value = Profile.parameters.get(name)
        return None if value is None else float(value)

    @staticmethod
    def paramBool(name: str):
        value = Profile.parameters.get(name)
        if value is None:
            return None
        return value.lower() == "true"

    def Apply(self):
        p = Profile.parameters
        p["sequenceMinSize"] = "6"
        p["sequenceMaxSize"] = "999"
        p["removeDuplicatesMethod"] = "1"
        p["consequentSize"] = "1"
        p["windowSize"] = "5"
        p["splitMethod"] = "0"
        p["splitLength"] = "999"
        p["recursiveDividerMin"] = "4"
        p["recursiveDividerMax"] = "99"
        p["minPredictionRatio"] = "2.0f"
        p["noiseRatio"] = "1.0f"
        p["firstVote"] = "1"
        p["secondVote"] = "2"
        p["voteTreshold"] = "0.0"
        p["countTableWeightMultiplier"] = "2"
        p["countTableWeightDivided"] = "1"
        p["useHashSidVisited"] = "true"
        p["branchTraversalTopToBottom"] = "true"
        p["removeUnknownItemsForPrediction"] = "true"

    @staticmethod
    def tostring() -> str:
        output = "---Global Parameters---\n"
        for k, v in Profile.parameters.items():
            output += f"{k}\t{v}\n"
        return output


class Paramable:
    def __init__(self) -> None:
        self.parameters: Dict[str, str] = {}

    def setParameter(self, params: str) -> None:
        if params and ":" in params:
            for param in params.split():
                keyValue = param.split(":")
                if len(keyValue) == 2:
                    self.parameters[keyValue[0]] = keyValue[1]

    def paramDouble(self, name: str):
        value = self.parameters.get(name)
        return float(value) if value is not None else Profile.paramDouble(name)

    def paramDoubleOrDefault(self, paramName: str, defaultValue: float) -> float:
        param = self.paramDouble(paramName)
        return param if param is not None else defaultValue

    def paramInt(self, name: str):
        value = self.parameters.get(name)
        return int(value) if value is not None else Profile.paramInt(name)

    def paramIntOrDefault(self, paramName: str, defaultValue: int) -> int:
        param = self.paramInt(paramName)
        return param if param is not None else defaultValue

    def paramFloat(self, name: str):
        value = self.parameters.get(name)
        return float(value) if value is not None else Profile.paramFloat(name)

    def paramFloatOrDefault(self, paramName: str, defaultValue: float) -> float:
        param = self.paramFloat(paramName)
        return param if param is not None else defaultValue

    def paramBool(self, name: str):
        value = self.parameters.get(name)
        return (value.lower() == "true") if value is not None else Profile.paramBool(name)

    def paramBoolOrDefault(self, paramName: str, defaultValue: bool) -> bool:
        param = self.paramBool(paramName)
        return param if param is not None else defaultValue


class Predictor:
    def __init__(self, tag: Optional[str] = None):
        self.TAG = tag

    def Train(self, trainingSequences: List[Sequence]):
        raise NotImplementedError

    def Predict(self, target: Sequence) -> Sequence:
        raise NotImplementedError

    def getTAG(self) -> str:
        return self.TAG

    def size(self) -> int:
        raise NotImplementedError

    def memoryUsage(self) -> float:
        raise NotImplementedError


@dataclass
class DGArc:
    dest: int
    support: int = 1


class DGNode:
    def __init__(self, value: int):
        self.value = value
        self.arcs: List[DGArc] = []
        self.totalSupport = 0
        self.numberOfArcs = 0

    def getArcCount(self) -> int:
        return len(self.arcs)

    def UpdOrAddArc(self, target: int) -> None:
        isFound = False
        for arc in self.arcs:
            if arc.dest == target:
                arc.support += 1
                isFound = True
        if not isFound:
            self.arcs.append(DGArc(target))


class SequenceDatabase:
    def __init__(self) -> None:
        self.sequences: List[Sequence] = []

    def setSequences(self, newSequences: List[Sequence]) -> None:
        self.sequences = list(newSequences)

    def getSequences(self) -> List[Sequence]:
        return self.sequences

    def size(self) -> int:
        return len(self.sequences)

    def clear(self) -> None:
        self.sequences.clear()

    def loadFileSPMFFormat(self, path: str, maxCount: int, minSize: int, maxSize: int) -> None:
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for thisLine in f:
                if count >= maxCount:
                    break
                sequence = Sequence(len(self.sequences))
                for entier in thisLine.strip().split(" "):
                    if entier == "-1":
                        pass
                    elif entier == "-2":
                        if minSize <= sequence.size() <= maxSize:
                            self.sequences.append(sequence)
                            count += 1
                    else:
                        sequence.getItems().append(Item(int(entier)))


class SequenceStatsGenerator:
    @staticmethod
    def prinStats(database: SequenceDatabase, name: str) -> None:
        print(f"---{name}---")
        print(f"Number of sequences : \t{database.size()}")

        maxItem = 0
        items = set()
        sizes: List[int] = []
        differentitems: List[int] = []
        appearXtimesbySequence: List[int] = []

        for sequence in database.getSequences():
            sizes.append(sequence.size())
            mapIntegers: Dict[int, int] = {}
            for item in sequence.getItems():
                count = mapIntegers.get(item.val, 0) + 1
                mapIntegers[item.val] = count
                items.add(item.val)
                if item.val > maxItem:
                    maxItem = item.val
            differentitems.append(len(mapIntegers))
            for count in mapIntegers.values():
                appearXtimesbySequence.append(count)

        print(f"Number of distinct items: \t{len(items)}")
        print(f"Largest item id: \t{maxItem}")
        print(f"Itemsets per sequence: \t{SequenceStatsGenerator.calculateMean(sizes)}")
        print(f"Distinct item per sequence: \t{SequenceStatsGenerator.calculateMean(differentitems)}")
        print(f"Occurences for each item: \t{SequenceStatsGenerator.calculateMean(appearXtimesbySequence)}")
        dataset_mb = ((database.size() * 4.0) + (database.size() * SequenceStatsGenerator.calculateMean(sizes) * 4.0) / (1000 * 1000))
        print(f"Size of the dataset in MB: \t{dataset_mb}")
        print()

    @staticmethod
    def calculateMean(values: List[int]) -> float:
        return sum(values) / len(values)


class DGPredictor(Predictor):
    def __init__(self, tag: str = "DG", params: Optional[str] = None):
        super().__init__(tag)
        self.mDictionary: Dict[int, DGNode] = {}
        self.parameters = Paramable()
        self.lookahead = 4
        if params is not None:
            self.parameters.setParameter(params)

    def Train(self, trainingSequences: List[Sequence]):
        w = self.parameters.paramIntOrDefault("lookahead", self.lookahead)
        self.mDictionary = {}
        for seq in trainingSequences:
            items = seq.getItems()
            for i in range(0, len(items) - 1):
                node = self.mDictionary.get(items[i].val)
                if node is None:
                    node = DGNode(items[i].val)
                node.totalSupport += 1
                for k in range(i + 1, min((i + 1) + w, len(items))):
                    node.UpdOrAddArc(items[k].val)
                self.mDictionary[items[i].val] = node
        return None

    def Predict(self, target: Sequence) -> Sequence:
        threshold = 0.12
        node = None
        for offset in range(target.size()):
            if node is None:
                lastItem = target.get(target.size() - (1 + offset))
                node = self.mDictionary.get(lastItem.val)
        if node is None:
            return Sequence(-1)

        max_score = 0.0
        best = 0
        for arc in node.arcs:
            score = float(arc.support) / node.totalSupport
            if score >= threshold and score > max_score:
                max_score = score
                best = arc.dest

        if best == 0:
            return Sequence(-1)

        predicted = Sequence(-1)
        predicted.addItem(Item(best))
        return predicted

    def size(self) -> int:
        nodeCount = 0
        for node in self.mDictionary.values():
            nodeCount += 1 + node.getArcCount()
        return nodeCount

    def memoryUsage(self) -> float:
        size = 0.0
        for node in self.mDictionary.values():
            size += 4 + (8 * node.getArcCount())
        return size


def main():
    input_file = "contextCPT.txt"
    path = Path(input_file)
    if not path.exists():
        print(f"Input file not found: {input_file}")
        print("Please place contextCPT.txt in the same folder as this Python file.")
        return

    trainingSet = SequenceDatabase()
    trainingSet.loadFileSPMFFormat(str(path), 2**31 - 1, 0, 2**31 - 1)

    print("--- Training sequences ---")
    for sequence in trainingSet.getSequences():
        print(sequence)
    print()

    SequenceStatsGenerator.prinStats(trainingSet, " training sequences ")

    optionalParameters = "lookahead:2"
    predictionModel = DGPredictor("DG", optionalParameters)
    predictionModel.Train(trainingSet.getSequences())

    sequence = Sequence(0)
    sequence.addItem(Item(1))
    sequence.addItem(Item(4))

    thePrediction = predictionModel.Predict(sequence)
    print(f"For the sequence <(1),(4)>, the prediction for the next symbol is: +{thePrediction}")


if __name__ == "__main__":
    main()
