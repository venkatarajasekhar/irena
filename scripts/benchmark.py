#!/usr/bin/python
import sys
import os
import re
import ConfigParser
import datetime
import string
import collections
import time
import shutil

if sys.platform == 'win32':
	BLUE=""
	RED=""
	YELLOW=""
	GREEN=""
	EC=""
else:
	BLUE="\033[34;1m"
	RED="\033[31;1m"
	YELLOW="\033[33;1m"
	GREEN="\033[32;1m"
	EC="\033[0;m"

def getstatusoutput(cmd): 
    """Return (status, output) of executing cmd in a shell."""
    """This new implementation should work on all platforms."""
    import subprocess
    pipe = subprocess.Popen(cmd, shell=True, universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = str.join("", pipe.stdout.readlines()) 
    sts = pipe.wait()
    if sts is None:
        sts = 0
    return sts, output	
	
def str2bool(v):
	  return v.lower() in ("yes", "true", "t", "y", "1")

class Video:
	def __init__(self, path, width, height, fmt):
		self.Width = width
		self.Height = height
		self.Format = fmt
		self.Path = path
	
	def get_name(self):
		base = os.path.basename(self.Path)
		return os.path.splitext(base)[0]


class Config:
	def __init__(self):
		self.Videos = list()
		self.ConfigParser = ConfigParser.RawConfigParser()

	def _get_config(self, section, name):
		try:
			ret = self.ConfigParser.get(sys.platform, name)
		except:
			try:
				ret = self.ConfigParser.get(section, name)
			except:
				print "Can not find option {0} in sections {1}, {2}".format(name, section, sys.platform)
				exit(1)
		return ret

	def parse_config(self, config_file):
		self.File = config_file
		self.ConfigParser.read(config_file)
		# General configuration
		self.Encoder = self._get_config('General', 'Encoder')
		self.EncoderArgs = self._get_config('General', 'EncoderArgs')
		self.Decoder = self._get_config('General', 'Decoder')
		self.DecoderArgs = self._get_config('General', 'DecoderArgs')
		self.PSNR = self._get_config('General', 'PSNR')
		self.PSNRArgs = self._get_config('General', 'PSNRArgs')
		self.Info = self._get_config('General', 'Info')
		self.InfoArgs = self._get_config('General', 'InfoArgs')
		self.Tar = self._get_config('General', 'Tar')
		self.Sleep = float(self._get_config('General', 'Sleep'))
		# Output configuration
		self.TarDecoded = str2bool(self._get_config('Output', 'TarDecoded')) and self.Tar != ""		
		self.ResultsDir = self._get_config('Output', 'ResultsDir')
		self.wildcard_results_dir()
		self.ResultsName = self._get_config('Output', 'ResultsName')
		self.RemoveDecoded = str2bool(self._get_config('Output', 'RemoveDecoded'))
		self.RemoveEncoded = str2bool(self._get_config('Output', 'RemoveEncoded'))
		self.ComputePSNR = str2bool(self._get_config('Output', 'ComputePSNR'))
		self.WriteSysInfo = str2bool(self._get_config('Output', 'WriteSysInfo'));
		self.SysInfoName = self._get_config('Output', 'SysInfoName')
		# Input Configuration
		self._videos_dir = self._get_config('Input', 'VideosDir')
		self._videos_ext = self._get_config('Input', 'VideosExt')
		self.VideosFormat = self._get_config('Input', 'VideosFormat')
		self.parse_videos()
		# Options configuration
		self.InterpolationScale = string.split(self._get_config('Options', 'Interpolation'), ' ')
		self.Huffman = string.split(self._get_config('Options', 'Huffman'), ' ')
		self.EncoderVariant = string.split(self._get_config('Options', 'EncoderVariant'), ' ')
		self.GOP = string.split(self._get_config('Options', 'GOP'), ' ')
		self.Q = string.split(self._get_config('Options', 'Q'), ' ')
		self.Device = string.split(self._get_config('Options', 'Device'), ' ')

	def get_count(self):
		r = 1
		r *= len(self.Videos)
		r *= len(self.InterpolationScale)
		r *= len(self.Huffman)
		r *= len(self.EncoderVariant)
		r *= len(self.GOP)
		r *= len(self.Q)
		r *= len(self.Device)
		return r
	
	def wildcard_results_dir(self):
		now = datetime.datetime.now()
		date = now.strftime("%Y%m%d")
		time = now.strftime("%H%M%S")
		self.ResultsDir = self.ResultsDir.replace("%d", date).replace("%t", time).replace('%p', sys.platform)

	def print_videos(self):
		print "Directory: {0}".format(self._videos_dir)
		for v in self.Videos:
			print "Video: [{0}x{1}] {2}".format(v.Width, v.Height, v.Path)

	def parse_videos(self):
		for d in os.listdir(self._videos_dir):
			#print "Parsing resolution: {0}".format(d)
			absdir = os.path.join(self._videos_dir, d)
			self.parse_resolution(absdir)

	def parse_resolution(self, dir):
		m = re.search('(?P<W>[0-9]+)x(?P<H>[0-9]+)', dir)
		width = m.group('W')
		height = m.group('H')
		for f in os.listdir(dir):
			#print "Parsing file: {0}".format(f)
			absf = os.path.join(dir, f)
			if os.path.isfile(absf) and f.endswith(self._videos_ext):
				v = Video(absf, width, height, "YUV420")
				self.Videos.append(v)

class Command:
	def __init__(self, cmd):
		self.Command = cmd
		self._exit = 0
		self._stdout = ""

	def add_arg(self, arg):
		self.Command += " " + arg
	
	def add_option(self, arg, val):
		self.Command += " " + arg + " " + val

	def get_status(self):
		return self._exit

	def get_stdout(self):
		return self._stdout

	def run(self):
		[s, o] = getstatusoutput(self.Command)
		self._exit = s
		self._stdout = o

class EncoderConfig:
	def __init__(self, video, variant, interpol, huffman, gop, q, device):
		self.Video = video
		self.Variant = variant
		self.InterpolationScale = interpol
		self.Huffman = huffman
		self.GOP = gop
		self.Q = q
		self.Device = device
	
	def get_video_variant(self):
		return self.Video.get_name() + self.get_variant()

	def get_variant(self):
		s = "_"
		s += "V"+self.Variant
		s += "H"+self.Huffman
		s += "I"+self.InterpolationScale
		s += "G"+self.GOP
		s += "Q"+self.Q
		s += "D"+self.Device
		return s

class Benchmark:
	SEPARATOR_LEN = 40
	def __init__(self, config):
		self.Config = config
		if not os.path.exists(self.Config.ResultsDir):
			os.makedirs(self.Config.ResultsDir)
		shutil.copy(self.Config.File, os.path.join(self.Config.ResultsDir, "benchmark.conf"))
		self.flog = open(os.path.join(self.Config.ResultsDir, "benchmark.log"), 'w')
		self.Results = list()

	def _write_sysinfo(self):
		cmd = Command(self.Config.Info)
		cmd.add_arg(self.Config.InfoArgs)
		cmd.run()
		if cmd.get_status() == 0:
			fh = open(os.path.join(self.Config.ResultsDir,self.Config.SysInfoName), "w")
			fh.write(cmd.get_stdout())
			fh.close()


	def run(self):
		if self.Config.WriteSysInfo:
			self._write_sysinfo()
		print BLUE + "Running benchmark"+ EC
		i = 1
		for D in self.Config.Device:
			for H in self.Config.Huffman:		
				for Q in self.Config.Q:
					for G in self.Config.GOP:
						for I in self.Config.InterpolationScale:
							for V in self.Config.EncoderVariant:
								for v in self.Config.Videos:
									cfg = EncoderConfig(v, V, I, H, G, Q, D)
									self._run_item(cfg, i)
									i = i+1
	
	def save_results(self):
		resf = open(os.path.join(self.Config.ResultsDir, self.Config.ResultsName), 'w')
		self._write_csv_header(resf)
		for r in self.Results:
			r.create_dict()
			for i in r.Dict:
				self._write_csv(resf, r.Dict[i])
			resf.write('\n')
		resf.close()

	def _log(self, data):
		self.flog.write(data)
	
	def _log_gsep(self):
		self.flog.write('='*self.SEPARATOR_LEN+"\n")
	
	def _log_lsep(self):
		self.flog.write('-'*self.SEPARATOR_LEN+"\n")

	def _out(self, data):
		sys.stdout.write(data)
		sys.stdout.flush()

	def _out_progress(self, txt):
		self._out("[{0}] {1}...".format("..", txt))

	def _out_done(self, txt, res):
		if res:
			self._out_error(txt)
		else:
			self._out(("\r[" + GREEN + "{0}" + EC + "] {1}...\n").format("OK", txt))
	
	def _out_error(self, txt):
		self._out(("\r[" + RED + "{0}" + EC + "] {1}...\n").format("ERROR", txt))

	def _run_encoder(self, cfg, bstr):
		self._out_progress("Encoding")
		cmd = Command(self.Config.Encoder)
		cmd.add_arg(self.Config.EncoderArgs)
		cmd.add_option("--interpolation", cfg.InterpolationScale)
		cmd.add_option("--huffman", cfg.Huffman)
		cmd.add_option("--variant", cfg.Variant)
		cmd.add_option("--gop", cfg.GOP)
		cmd.add_option("--quant", cfg.Q)
		cmd.add_option("--device", cfg.Device)
		self._append_video(cfg.Video, cmd, bstr)
		self._log_lsep()
		self._log(cmd.Command+'\n')
		cmd.run()
		stdout = cmd.get_stdout()
		self._log_lsep()
		self._log(stdout+'\n')
		self._out_done("Encoding", cmd.get_status())
		return stdout

	def _parse_results(self, cfg, data):
		self._out_progress("Parsing results")
		result = Result(cfg, self.Config.PSNR)
		result.parse(data)
		self.Results.append(result)
		self._out_done("Parsing results", 0)
		
	def _run_decoder(self, output, bstr):
		self._out_progress("Decoding")
		cmd = Command(self.Config.Decoder)
		cmd.add_arg(self.Config.DecoderArgs)
		cmd.add_option("--output", output)
		cmd.add_arg(bstr)
		self._log_lsep()
		self._log(cmd.Command+'\n')
		cmd.run()
		stdout = cmd.get_stdout()
		self._log_lsep()
		self._log(stdout+'\n')
		self._out_done("Decoding", cmd.get_status())
	
	def _run_psnr(self, cfg, output):
		self._out_progress("Computing PSNR")
		self._log_lsep()
		cmd = Command(self.Config.PSNR)
		cmd.add_arg(self.Config.PSNRArgs)
		cmd.add_option("--gop", cfg.GOP)
		cmd.add_option("--type", self.Config.VideosFormat)
		cmd.add_option("--height", cfg.Video.Height)
		cmd.add_option("--width", cfg.Video.Width)
		cmd.add_arg(cfg.Video.Path)
		cmd.add_arg(output)
		self._log(cmd.Command+'\n')
		cmd.run()
		stdout = cmd.get_stdout()
		self._log_lsep()
		self._log(stdout+'\n')
		self._out_done("Computing PSNR", cmd.get_status())
		return stdout

	def _run_tar(self, tar, output):
		self._out_progress("Compressing")
		self._log_lsep()
		tarcmd = self.Config.Tar.replace('%O', tar).replace('%I', output)
		cmd = Command(tarcmd)
		self._log(cmd.Command+'\n')
		cmd.run()
		self._out_done("Compressing", cmd.get_status())

	def _sleep(self):
		self._out_progress("Sleep")
		time.sleep(self.Config.Sleep)
		self._out_done("Sleep", 0)
	
	def _remove_output(self, output):
		self._out_progress("Removing decoded video")
		os.remove(output)
		self._out_done("Removing decoded video", 0)
	
	def _remove_encoded(self, bstr):
		self._out_progress("Removing encoded bitstream")
		os.remove(bstr)
		self._out_done("Removing encoded bitstream", 0)
	
	def _run_item(self, cfg, i):
		self._log_gsep()
		self._log("Run {0}/{1}\n".format(i, self.Config.get_count()))
		self._out((YELLOW + "Run {0}/{1}" + EC + "\n").format(i, self.Config.get_count()))
		bstr = self._get_out_path(cfg.get_video_variant() + ".bstr")
		output = self._get_out_path(cfg.get_video_variant() + ".yuv")
		tar = self._get_out_path(cfg.get_video_variant())
		stdout = self._run_encoder(cfg, bstr) 
		self._run_decoder(output, bstr)
		if self.Config.ComputePSNR:
			stdout = stdout + self._run_psnr(cfg, output)
		self._parse_results(cfg, stdout)
		if self.Config.TarDecoded:
			self._run_tar(tar, output)
		if self.Config.RemoveDecoded:
			self._remove_output(output)
		if self.Config.RemoveEncoded:
			self._remove_encoded(bstr)
		if self.Config.Sleep > 0:
			self._sleep()

	def _get_out_path(self, name):
		return os.path.join(self.Config.ResultsDir, name)

	def _append_video(self, video, cmd, output):
		cmd.add_option("--type", self.Config.VideosFormat)
		cmd.add_option("--height", video.Height)
		cmd.add_option("--width", video.Width)
		cmd.add_option("--output", output)
		cmd.add_arg(video.Path)

	def _write_csv(self, resf, data):
		resf.write(data + ';')
	
	def _write_csv_header(self, resf):
		if len(self.Results) > 0:
			r = self.Results[0]
			r.create_dict()
			for i in r.Dict:
				self._write_csv(resf, i)
			resf.write("\n")


class ResultItem:
	INVALID = ""
	TYPE_TEXT = 0
	TYPE_FLOAT = 1
	TYPE_INT = 2
	def __init__(self, desc, reg, t):
		self.Value = self.INVALID
		self.Description = desc
		self._reg = reg
		self.Type = t

	def parse(self, data):
		if self.Value == self.INVALID:
			m = re.search(self._reg, data)
			if m != None:
				self.Value = m.group('v')
				if self.Type == self.TYPE_FLOAT:
					self.Value = self.Value.replace('.', ',')


class Result:
	def __init__(self, cfg, psnr):
		self.EncoderConfig = cfg
		self.Items = list()
		self.Dict = collections.OrderedDict()
		self.create_int_item("Numer of frames")
		self.create_file_size_item("Original file size")
		self.create_file_size_item("Compressed file size")
		self.create_float_item("Compression ratio")
		self.create_result_item_timer("Total")
		self.create_result_item_timer("DCT")
		self.create_result_item_timer("IDCT")
		self.create_result_item_timer("Quant")
		self.create_result_item_timer("IQuant")
		self.create_result_item_timer("Zig Zag")
		self.create_result_item_timer("DCTQZZ")
		self.create_result_item_timer("IDCTQ")
		self.create_result_item_timer("RLC")
		self.create_result_item_timer("Prediction")
		self.create_result_item_timer("P FRAME Transform")
		self.create_result_item_timer("P FRAME ITransform")
		self.create_result_item_timer("Interpolation")
		self.create_result_item_timer("Copy Last Image")
		self.create_result_item_timer("Encode Prediction")
		self.create_result_item_timer("Shift +128")
		self.create_result_item_timer("Shift -128")
		self.create_result_item_timer("Copy to host")
		self.create_result_item_timer("Copy to device")
		self.create_result_item_timer("Copy buffer")
		self.create_result_item_timer("Kernel finish")
		self.create_result_item_timer("Enqueue kernel")
		if psnr:
			self.create_result_psnr("Y PSNR")
			self.create_result_psnr("U PSNR")
			self.create_result_psnr("V PSNR")
			self.create_result_psnr("Y PSNR for I frames")
			self.create_result_psnr("U PSNR for I frames")
			self.create_result_psnr("V PSNR for I frames")
			self.create_result_psnr("Y PSNR for P frames")
			self.create_result_psnr("U PSNR for P frames")
			self.create_result_psnr("V PSNR for P frames")
	
	def create_int_item(self, name):
		r = "{0}\s*:\s*(?P<v>[0-9]+)".format(name)
		self.Items.append(ResultItem(name, r, ResultItem.TYPE_INT))
	
	def create_file_size_item(self, name):
		r = "{0}\s*:\s*(?P<v>[0-9]+) b".format(name)
		self.Items.append(ResultItem(name, r, ResultItem.TYPE_INT))

	def create_float_item(self, name):
		self.Items.append(ResultItem(name, self.create_regex_float(name), ResultItem.TYPE_FLOAT))

	def create_result_psnr(self, name):
		self.Items.append(ResultItem(name, self.create_regex_float(name), ResultItem.TYPE_FLOAT))

	def create_result_item_timer(self, name):
		self.Items.append(ResultItem(name, self.create_regex_float("Timer " + name), ResultItem.TYPE_FLOAT))

	def create_regex_float(self, text):
		text = text.replace("+", "\+")
		return "{0}\s*:\s*(?P<v>[0-9]+\.[0-9]+)".format(text)
	
	def create_dict(self):
		self.Dict['Sequence'] = self.EncoderConfig.Video.get_name()
		self.Dict['Variant'] = self.EncoderConfig.Variant
		self.Dict['InterpolationScale'] = self.EncoderConfig.InterpolationScale
		self.Dict['Huffman'] = self.EncoderConfig.Huffman
		self.Dict['GOP'] = self.EncoderConfig.GOP
		self.Dict['Q'] = self.EncoderConfig.Q
		self.Dict['Device'] = self.EncoderConfig.Device
		for i in self.Items:
			self.Dict[i.Description] = i.Value

	def parse(self, data):
		for item in self.Items:
			item.parse(data)


def main():
	argc = len(sys.argv)
	config_file = "benchmark.conf"
	if argc == 2:
		if os.path.exists(sys.argv[1]) and os.path.isfile(sys.argv[1]):
			config_file = sys.argv[1]
		else:
			print "{0}: directory not exists".format(sys.argv[1])
	config = Config()
	config.parse_config(config_file)
	benchmark = Benchmark(config)
	benchmark.run()
	benchmark.save_results()
	

if __name__ == '__main__':
	try:
		main()
	except:
		print "error: ", sys.exc_info()[1]

