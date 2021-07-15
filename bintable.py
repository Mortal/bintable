#!/usr/bin/env python3

import argparse
import io
import json
import os
from typing import BinaryIO, List

import astropy.table
import astropy.units
import numpy as np


def _read_partial_vot(filename: str, bytes: int) -> bytes:
    with open(filename, "rb") as fp:
        data = fp.read(bytes)
    i = data.rindex(b"</TR>")
    return data[:i] + b"</TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"


def write(table: astropy.table.Table, path: str) -> None:
    datafiles = {}
    columns = []
    maskdatas = []
    masklength = 0
    for k in table.colnames:
        col = table.columns[k]
        if col.dtype.char in ("S", "U"):
            datafile = datafiles.setdefault(
                "text", {"name": "data.text.json", "datas": [], "length": 0}
            )
        else:
            dt = str(col.dtype)
            assert "<" not in dt
            datafile = datafiles.setdefault(
                dt, {"name": f"data.{dt}.npy", "datas": [], "length": 0}
            )
        i = datafile["length"]
        n, = col.data.shape
        datafile["length"] += n
        if datafile["name"].endswith(".json"):
            datafile["datas"] += col.data.tolist()
        else:
            datafile["datas"].append(col.data.data)
        column = {"name": k, "file": datafile["name"], "offset": i, "length": n}
        if table.masked and np.any(col.mask):
            column["maskoffset"] = masklength
            assert col.mask.shape == (n,)
            maskdatas.append(col.mask)
            masklength += n
        if col.unit is not None:
            column["unit"] = str(col.unit)
        columns.append(column)

    if os.path.exists(path):
        if not os.path.exists(
            os.path.join(path, "bintable.json_")
        ) and not os.path.exists(os.path.join(path, "bintable.json_")):
            raise FileExistsError(path)
    else:
        os.mkdir(path)
    with open(os.path.join(path, "bintable.json_"), "w") as fp:
        fp.write(
            json.dumps(
                {"meta": table.meta, "masked": bool(table.masked), "columns": columns},
                indent=2,
            )
        )
    if maskdatas:
        np.save(
            os.path.join(path, "mask.npy"),
            np.concatenate(maskdatas),
            allow_pickle=False,
        )
    for dt, df in datafiles.items():
        if df["name"].endswith(".json"):
            with open(os.path.join(path, df["name"]), "w") as fp:
                fp.write(json.dumps(df["datas"], indent=0))
        else:
            np.save(
                os.path.join(path, df["name"]),
                np.concatenate(df["datas"]),
                allow_pickle=False,
            )
    os.rename(os.path.join(path, "bintable.json_"), os.path.join(path, "bintable.json"))


def read(path: str, *, only_columns: List[str] = None) -> astropy.table.Table:
    with open(os.path.join(path, "bintable.json")) as fp:
        bintable = json.load(fp)
    names = []
    meta = bintable["meta"]
    masked = bintable["masked"]
    data = []
    backing = {}
    maskedbacking = None
    columns = bintable["columns"]
    if only_columns is not None:
        coldict = {c["name"]: c for c in columns}
        columns = [coldict[n] for n in only_columns]
    units = {}
    unitcache = {}
    for column in columns:
        names.append(column["name"])
        if column["file"] not in backing:
            assert "/" not in column["file"]
            if column["file"].endswith(".npy"):
                backing[column["file"]] = np.load(
                    os.path.join(path, column["file"]),
                    mmap_mode="r",
                    allow_pickle=False,
                )
            elif column["file"].endswith(".json"):
                with open(os.path.join(path, column["file"])) as fp:
                    backing[column["file"]] = json.load(fp)
        a = backing[column["file"]]
        a = a[column["offset"] : column["offset"] + column["length"]]
        if "maskoffset" in column:
            if maskedbacking is None:
                maskedbacking = np.load(
                    os.path.join(path, "mask.npy"), mmap_mode="r", allow_pickle=False
                )
            a = np.ma.masked_array(
                a,
                maskedbacking[
                    column["maskoffset"] : column["maskoffset"] + column["length"]
                ],
            )
        data.append(a)
        if "unit" in column:
            unit_string = column["unit"]
            try:
                unit = unitcache[unit_string]
            except KeyError:
                try:
                    unit = unitcache[unit_string] = astropy.units.Unit(unit_string)
                except ValueError:
                    unit = unitcache[unit_string] = astropy.units.def_unit(unit_string)
            units[column["name"]] = unit
    table = astropy.table.Table(
        names=names, meta=meta, masked=masked, copy=False, data=data
    )
    for k, u in units.items():
        assert k in names
        table.columns[k].unit = u
    return table


parser = argparse.ArgumentParser()
parser.add_argument("--input", "-i", required=True)
parser.add_argument("--input-type", help="Use astropy.table.Table.read(..., format=<INPUT-TYPE>)")
parser.add_argument("--input-truncate", type=int, help="Don't read more than this number of bytes (votable only)")
parser.add_argument("--input-columns", help="Comma-separated list of columns to read (bintable only)")
parser.add_argument("--output", "-o")
parser.add_argument("--output-type", help="Use astropy.table.Table.write(..., format=<INPUT-TYPE>)")


def main() -> None:
    args = parser.parse_args()
    if args.input_type is not None:
        table = astropy.table.Table.read(args.input, format=args.input_type)
    elif args.input.endswith(".vot") and os.path.isfile(args.input):
        if args.input_truncate is not None:
            d = _read_partial_vot(args.input, args.input_truncate)
            fp: BinaryIO = io.BytesIO(d)
        else:
            fp = open(args.input, "rb")
        with fp as fp:
            table = astropy.table.Table.read(fp, format="votable")
    elif os.path.isdir(args.input) and os.path.isfile(os.path.join(args.input, "bintable.json")):
        table = read(args.input, only_columns=None if args.input_columns is None else args.input_columns.split(","))
    else:
        raise SystemExit("Unknown input format")
    if args.output is None:
        return
    if args.output_type is not None:
        table.write(args.output, format=args.output_type)
    elif args.output.endswith(".vot"):
        table.write(args.output, format="votable")
    elif "." not in os.path.basename(args.output):
        write(table, args.output)
    else:
        raise SystemExit("Unknown output format")


if __name__ == "__main__":
    main()
