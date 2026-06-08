#!/usr/bin/env python3
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict, List, Optional


class Item:
    def __init__(self, value: Optional[int] = None):
        self.val = -1 if value is None else int(value)

    def clone(self) -> "Item":
        return Item(self.val)

    def __str__(self) -> str:
        return str(self.val)

    def __hash__(self) -> int:
        return hash(self.val)

    def __eq__(self, other) -> bool:
        return isinstance(other, Item) and self.val == other.val

    def compareTo(self, other: "Item") -> int:
        return (self.val > other.val) - (self.val < other.val)


class Sequence:
    def __init__(self, id_: int, items: Optional[List[Item]] = None):
        self.id = id_
        self.items: List[Item] = items if items is not None else []

    @staticmethod
    def fromString(sequenceId: int, input_str: str) -> "Sequence":
        sequence = Sequence(sequenceId)
        if input_str is not None and len(input_str) > 0:
            for item in input_str.split():
                sequence.addItem(Item(int(item)))
        return sequence

    def getId(self) -> int:
        return self.id

    def getItems(self) -> List[Item]:
        return self.items

    def setItems(self, newItems: List[Item]) -> None:
        self.items = newItems

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
            truncatedList = list(self.items[0:size])
            truncatedSequence.setItems(truncatedList)
        else:
            truncatedList = list(self.items[(size - length):size])
            truncatedSequence.setItems(truncatedList)

        return truncatedSequence

    def print(self) -> None:
        print(str(self), end="")

    def __str__(self) -> str:
        r = []
        for it in self.items:
            r.append("(")
            r.append(str(it))
            r.append(") ")
        r.append("    ")
        return "".join(r)

    def setID(self, newid: int) -> None:
        self.id = newid

    def clone(self) -> "Sequence":
        copy = Sequence(self.id)
        for item in self.items:
            copy.items.append(item.clone())
        return copy

    def __eq__(self, other) -> bool:
        if not isinstance(other, Sequence):
            return False
        if self.id != other.id or len(self.items) != len(other.items):
            return False
        for i in range(len(self.items)):
            if self.items[i] != other.items[i]:
                return False
        return True

    def __hash__(self) -> int:
        return hash((self.id, tuple(self.items)))


class Profile:
    parameters: Dict[str, str] = {}

    def __init__(self):
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
        p["minPredictionRatio"] = "2.0"
        p["noiseRatio"] = "1.0"
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
        nl = "\n"
        output = "---Global Parameters---" + nl
        for k, v in Profile.parameters.items():
            output += f"{k}\t{v}{nl}"
        return output


class SequenceDatabase:
    def __init__(self):
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
        with open(path, "r", encoding="utf-8") as myInput:
            for thisLine in myInput:
                if count >= maxCount:
                    break
                thisLine = thisLine.strip()
                if not thisLine:
                    continue
                sequence = Sequence(len(self.sequences))
                for entier in thisLine.split(" "):
                    if entier == "-1":
                        pass
                    elif entier == "-2":
                        if sequence.size() >= minSize and sequence.size() <= maxSize:
                            self.sequences.append(sequence)
                            count += 1
                    else:
                        val = int(entier)
                        sequence.getItems().append(Item(val))


class SequenceStatsGenerator:
    @staticmethod
    def prinStats(database: SequenceDatabase, name: str) -> None:
        print("---" + name + "---")
        print("Number of sequences : \t" + str(database.size()))

        maxItem = 0
        items = set()
        sizes: List[int] = []
        differentitems: List[int] = []
        appearXtimesbySequence: List[int] = []

        for sequence in database.getSequences():
            sizes.append(sequence.size())
            mapIntegers: Dict[int, int] = {}

            for item in sequence.getItems():
                count = mapIntegers.get(item.val, 0)
                count += 1
                mapIntegers[item.val] = count
                items.add(item.val)
                if item.val > maxItem:
                    maxItem = item.val

            differentitems.append(len(mapIntegers))
            for value in mapIntegers.values():
                appearXtimesbySequence.append(value)

        print("Number of distinct items: \t" + str(len(items)))
        print("Largest item id: \t" + str(maxItem))
        print("Itemsets per sequence: \t" + str(SequenceStatsGenerator.calculateMean(sizes)))
        print("Distinct item per sequence: \t" + str(SequenceStatsGenerator.calculateMean(differentitems)))
        print("Occurences for each item: \t" + str(SequenceStatsGenerator.calculateMean(appearXtimesbySequence)))
        size_mb = ((database.size() * 4.0) + (database.size() * SequenceStatsGenerator.calculateMean(sizes) * 4.0) / (1000 * 1000))
        print("Size of the dataset in MB: \t" + str(size_mb))
        print()

    @staticmethod
    def calculateMean(lst: List[int]) -> float:
        return sum(lst) / len(lst)


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


class LZNode:
    def __init__(self, value: int):
        self.value = value
        self.children = set()
        self.support = 1
        self.childSumSupport = 0

    def addChild(self, child: int) -> None:
        self.children.add(child)
        self.incChildSupport()

    def incChildSupport(self) -> None:
        self.childSumSupport += 1

    def inc(self) -> None:
        self.support += 1

    def getSup(self) -> int:
        return self.support

    def getChildSup(self) -> int:
        return self.childSumSupport


class LZ78Predictor(Predictor):
    def __init__(self, tag: Optional[str] = None):
        super().__init__(tag if tag is not None else "LZ78")
        self.count = 0
        self.order = 0
        self.mDictionary: Dict[tuple, LZNode] = {}

    def Train(self, trainingSequences: List[Sequence]):
        self.mDictionary = {}
        self.order = 0
        self.count = 0

        for seq in trainingSequences:
            items = seq.getItems()
            prefix: List[int] = []
            offset = 0

            while offset < len(items):
                cur = items[offset].val
                lzPhrase = list(prefix)
                lzPhrase.append(cur)
                key = tuple(lzPhrase)

                node = self.mDictionary.get(key)
                if node is not None:
                    node.inc()
                    self.mDictionary[key] = node

                    if len(lzPhrase) > self.order:
                        self.order = len(lzPhrase)

                    if len(prefix) > 0 and tuple(prefix) in self.mDictionary:
                        self.mDictionary[tuple(prefix)].incChildSupport()

                    prefix.append(cur)
                else:
                    if len(prefix) > 0 and tuple(prefix) in self.mDictionary:
                        self.mDictionary[tuple(prefix)].addChild(cur)

                    self.mDictionary[key] = LZNode(cur)
                    prefix.clear()
                    self.count += 1

                offset += 1

        return True

    def Predict(self, target: Sequence) -> Sequence:
        results: Dict[int, float] = {}

        prefix: List[int] = []
        last_seq = target.getLastItems(self.order, 0)
        lastItems = last_seq.getItems() if last_seq is not None else []
        lastItems = list(lastItems)
        lastItems.reverse()

        for item in lastItems:
            prefix.insert(0, item.val)

            parent = self.mDictionary.get(tuple(prefix))
            if parent is None:
                continue

            escapeK = parent.getSup() - parent.getChildSup()

            for value in parent.children:
                lzPhrase = list(prefix)
                lzPhrase.append(value)
                child = self.mDictionary.get(tuple(lzPhrase))

                if child is not None:
                    probK1 = results.get(value, 0.0)
                    probK = (float(child.getSup()) / parent.getSup()) + (escapeK * probK1)
                    results[value] = probK

        highestScore = 0.0
        mostProbableItem = None
        for key in sorted(results.keys()):
            value = results[key]
            if value > highestScore:
                highestScore = value
                mostProbableItem = key

        predicted = Sequence(-1)
        if mostProbableItem is not None:
            predicted.addItem(Item(mostProbableItem))
        return predicted

    def size(self) -> int:
        return self.count

    def memoryUsage(self) -> float:
        size = 0.0
        for node in self.mDictionary.values():
            size += 12 + (4 * len(node.children))
        return size


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    inputPath = script_dir / "contextCPT.txt"
    modelPath = script_dir / "model.ser"

    if not inputPath.exists():
        print(f"Input file not found: {inputPath.name}")
        print("Please place contextCPT.txt in the same folder as this Python file.")
        return

    trainingSet = SequenceDatabase()
    trainingSet.loadFileSPMFFormat(str(inputPath), 2**31 - 1, 0, 2**31 - 1)

    print("--- Training sequences ---")
    for sequence in trainingSet.getSequences():
        print(sequence)
    print()

    SequenceStatsGenerator.prinStats(trainingSet, " Statistics about training sequences ")

    predictionModel = LZ78Predictor("LZ78")
    predictionModel.Train(trainingSet.getSequences())

    sequence = Sequence(0)
    sequence.addItem(Item(1))
    sequence.addItem(Item(4))

    print("--- Prediction ---")
    thePrediction = predictionModel.Predict(sequence)
    print("For the sequence <(1),(4)>, the prediction for the next symbol is: +" + str(thePrediction))

    with open(modelPath, "wb") as stream:
        pickle.dump(predictionModel, stream)

    with open(modelPath, "rb") as stream2:
        predictionModel2 = pickle.load(stream2)

    thePrediction2 = predictionModel2.Predict(sequence)
    print("For the sequence <(1),(4)>, the prediction for the next symbol is: +" + str(thePrediction2))


if __name__ == "__main__":
    main()
